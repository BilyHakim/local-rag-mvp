from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.documents import DocumentUploadResponse
from app.services.chunking_service import chunk_text
from app.services.dedup_service import compute_content_hash, document_point_id
from app.services.docx_service import extract_docx_pages
from app.services.ollama_service import ollama_service
from app.services.pdf_service import extract_pdf_pages
from app.services.qdrant_service import qdrant_service
from app.services.spreadsheet_service import extract_spreadsheet_pages


router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv"}


def _extract_document_pages(saved_path: Path, extension: str) -> list[dict]:
    if extension == ".pdf":
        return extract_pdf_pages(saved_path)

    if extension == ".docx":
        return extract_docx_pages(saved_path)

    if extension in {".xlsx", ".xls", ".csv"}:
        return extract_spreadsheet_pages(saved_path, extension)

    raise ValueError(f"Ekstensi file tidak didukung: {extension}")


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename kosong."
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="MVP ini support file PDF, DOCX, XLSX, XLS, dan CSV."
        )

    content = await file.read()
    content_hash = compute_content_hash(content)

    if qdrant_service.exists_by_content_hash(content_hash):
        existing = qdrant_service.get_sample_by_content_hash(content_hash)

        return DocumentUploadResponse(
            filename=file.filename,
            saved_path=(existing or {}).get("saved_path") or "",
            total_pages=0,
            total_chunks=0,
            indexed_chunks=0,
            content_hash=content_hash,
            skipped_duplicate=True,
            message="Dokumen identik sudah ter-index sebelumnya. Upload dilewati.",
        )

    documents_dir = Path(settings.STORAGE_DIR) / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{uuid4()}_{file.filename}"
    saved_path = documents_dir / safe_filename
    saved_path.write_bytes(content)

    try:
        qdrant_service.delete_by_filename(file.filename)

        pages = _extract_document_pages(saved_path, extension)

        total_chunks = 0
        indexed_chunks = 0
        source_format = extension.lstrip(".")

        for page in pages:
            page_number = page["page_number"]
            page_text = page["text"]
            extraction_method = page["extraction_method"]
            sheet_name = page.get("sheet_name")
            row_number = page.get("row_number")

            chunks = chunk_text(page_text)
            total_chunks += len(chunks)

            for chunk_index, chunk in enumerate(chunks):
                vector = await ollama_service.embed(chunk)
                point_id = document_point_id(
                    content_hash,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    row_number=row_number,
                    sheet_name=sheet_name,
                )

                qdrant_service.upsert_text(
                    vector=vector,
                    text=chunk,
                    source_name=file.filename,
                    metadata={
                        "source_type": f"{source_format}_{extraction_method}",
                        "filename": file.filename,
                        "saved_path": str(saved_path),
                        "page_number": page_number,
                        "chunk_index": chunk_index,
                        "file_format": source_format,
                        "extraction_method": extraction_method,
                        "sheet_name": sheet_name,
                        "row_number": row_number,
                        "content_hash": content_hash,
                    },
                    point_id=point_id,
                )

                indexed_chunks += 1

        return DocumentUploadResponse(
            filename=file.filename,
            saved_path=str(saved_path),
            total_pages=len(pages),
            total_chunks=total_chunks,
            indexed_chunks=indexed_chunks,
            content_hash=content_hash,
            skipped_duplicate=False,
            message="Dokumen berhasil di-index.",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses dokumen: {str(exc)}"
        )
