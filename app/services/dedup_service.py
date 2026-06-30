import hashlib
import uuid


DOCUMENT_POINT_NAMESPACE = uuid.UUID("c4e8a1f2-9b3d-4f6e-a7c1-2d5e8f9a0b3c")
KNOWLEDGE_POINT_NAMESPACE = uuid.UUID("d5f9b2a3-0c4e-5a7f-b8d2-3e6f9a0b1c4d")


def compute_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_text_hash(text: str, source_name: str | None = None) -> str:
    normalized = f"{source_name or ''}\n{text}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def document_point_id(
    content_hash: str,
    *,
    page_number: int,
    chunk_index: int,
    row_number: int | None = None,
    sheet_name: str | None = None,
) -> str:
    key = (
        f"{content_hash}|p{page_number}|c{chunk_index}"
        f"|r{row_number or 0}|s{sheet_name or ''}"
    )
    return str(uuid.uuid5(DOCUMENT_POINT_NAMESPACE, key))


def knowledge_point_id(content_hash: str) -> str:
    return str(uuid.uuid5(KNOWLEDGE_POINT_NAMESPACE, content_hash))
