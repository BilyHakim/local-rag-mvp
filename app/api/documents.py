from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.documents import DocumentUploadResponse
from app.services.chunking_service import chunk_text
from app.services.ollama_service import ollama_service
from app.services.pdf_service import extract_pdf_pages
from app.services.qdrant_service import qdrant_service


router = APIRouter()


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename kosong."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="MVP ini baru support file PDF."
        )

    documents_dir = Path(settings.STORAGE_DIR) / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{uuid4()}_{file.filename}"
    saved_path = documents_dir / safe_filename

    content = await file.read()
    saved_path.write_bytes(content)

    try:
        pages = extract_pdf_pages(saved_path)

        total_chunks = 0
        indexed_chunks = 0

        for page in pages:
            page_number = page["page_number"]
            page_text = page["text"]

            chunks = chunk_text(page_text)
            total_chunks += len(chunks)

            for chunk_index, chunk in enumerate(chunks):
                vector = await ollama_service.embed(chunk)

                qdrant_service.upsert_text(
                    vector=vector,
                    text=chunk,
                    source_name=file.filename,
                    metadata={
                        "source_type": "pdf",
                        "filename": file.filename,
                        "saved_path": str(saved_path),
                        "page_number": page_number,
                        "chunk_index": chunk_index,
                    }
                )

                indexed_chunks += 1

        return DocumentUploadResponse(
            filename=file.filename,
            saved_path=str(saved_path),
            total_pages=len(pages),
            total_chunks=total_chunks,
            indexed_chunks=indexed_chunks,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses PDF: {str(exc)}"
        )