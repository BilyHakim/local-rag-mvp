import re
from app.core.config import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    chunk_size = settings.CHUNK_SIZE if chunk_size is None else chunk_size
    overlap = settings.CHUNK_OVERLAP if overlap is None else overlap
    if not 0 <= overlap < chunk_size:
        raise ValueError("Require 0 <= overlap < chunk_size")

    clean_text = " ".join(text.split())

    if not clean_text:
        return []

    chunks = []
    start = 0
    text_length = len(clean_text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length:
            # Prefer a sentence/word boundary without allowing overlap to stall.
            minimum = max(start + overlap + 1, start + chunk_size // 2)
            boundaries = [m.end() for m in re.finditer(r"[.!?]\s+", clean_text[start:end])
                          if start + m.end() >= minimum]
            if boundaries:
                end = start + boundaries[-1]
            else:
                boundary = clean_text.rfind(" ", minimum, end)
                if boundary >= minimum:
                    end = boundary
        chunk = clean_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap

        if start < 0:
            start = 0

    return chunks
