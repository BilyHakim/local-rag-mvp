from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    filename: str
    saved_path: str
    total_pages: int
    total_chunks: int
    indexed_chunks: int
    content_hash: str | None = None
    skipped_duplicate: bool = False
    message: str | None = None
