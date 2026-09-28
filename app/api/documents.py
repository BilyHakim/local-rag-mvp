import asyncio
import hashlib
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from app.core.config import settings
from app.core.security import tenant_context
from app.schemas.documents import DocumentUploadResponse
from app.services.chunking_service import chunk_text
from app.services.docx_service import extract_docx_pages
from app.services.pdf_service import OCRUnavailableError, extract_pdf_pages
from app.services.spreadsheet_service import extract_spreadsheet_pages
from app.services.ingestion_service import ingest
from app.services.qdrant_service import qdrant_service

router = APIRouter()
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv"}


def _extract_document_pages(saved_path: Path, extension: str) -> list[dict]:
    with saved_path.open("rb") as stream:
        signature = stream.read(8)
    if extension == ".pdf":
        if not signature.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
        return extract_pdf_pages(saved_path)
    if extension in {".xlsx", ".docx"}:
        with zipfile.ZipFile(saved_path) as archive:
            if sum(i.file_size for i in archive.infolist()) > settings.MAX_UPLOAD_BYTES * 10:
                raise ValueError("Archive expanded size exceeds limit")
    if extension == ".xls" and signature != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise ValueError("Invalid XLS signature")
    if extension == ".docx":
        return extract_docx_pages(saved_path)
    return extract_spreadsheet_pages(saved_path, extension)


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    filename = Path((file.filename or "").replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "Format dokumen tidak didukung")
    directory = Path(settings.STORAGE_DIR) / "documents" / tenant_context.get()
    directory.mkdir(parents=True, exist_ok=True)
    saved_path = directory / f"{uuid4()}{extension}"
    digest = hashlib.sha256()
    size = 0
    published = False
    try:
        with saved_path.open("wb") as target:
            while block := await file.read(1024 * 1024):
                size += len(block)
                if size > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Ukuran dokumen melebihi batas")
                digest.update(block)
                target.write(block)
        content_hash = digest.hexdigest()
        existing = await asyncio.to_thread(qdrant_service.get_sample_by_content_hash, content_hash)
        if existing and existing.get("filename") == filename:
            return DocumentUploadResponse(filename=filename, saved_path="", total_pages=0,
                total_chunks=0, indexed_chunks=0, content_hash=content_hash, skipped_duplicate=True,
                message="Dokumen identik sudah aktif.")
        pages = await asyncio.to_thread(_extract_document_pages, saved_path, extension)
        records = []
        for page in pages:
            for index, chunk in enumerate(chunk_text(page["text"])):
                records.append({**page, "text": chunk, "chunk_index": index,
                    "filename": filename, "source_name": filename, "content_hash": content_hash,
                    "saved_path": str(saved_path),
                    "file_format": extension[1:], "source_type": f"{extension[1:]}_{page['extraction_method']}"})
                if len(records) > settings.MAX_CHUNKS:
                    raise ValueError("Chunk limit exceeded")
        await ingest(f"document:{filename}", records)
        published = True
        return DocumentUploadResponse(filename=filename, saved_path="", total_pages=len(pages),
            total_chunks=len(records), indexed_chunks=len(records), content_hash=content_hash,
            skipped_duplicate=False, message="Dokumen berhasil di-index.")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except OCRUnavailableError as exc:
        raise HTTPException(503, "OCR belum tersedia pada server") from exc
    finally:
        await file.close()
        if not published:
            saved_path.unlink(missing_ok=True)
