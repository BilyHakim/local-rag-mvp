"""Stage immutable points, then publish the entire source in one SQLite commit."""
import asyncio
import logging
import time
from uuid import uuid4

from app.core.config import settings
from app.services import index_manifest
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


async def ingest(source: str, records: list[dict], *, allow_empty=False) -> list[dict]:
    started = time.monotonic()
    if (not records and not allow_empty) or len(records) > settings.MAX_CHUNKS:
        raise ValueError("Document empty or chunk limit exceeded")
    await asyncio.to_thread(index_manifest.versions)
    version = str(uuid4())
    staged = [dict(item, id=str(uuid4())) for item in records]
    for offset in range(0, len(staged), settings.EMBED_BATCH_SIZE):
        batch = staged[offset:offset + settings.EMBED_BATCH_SIZE]
        vectors = await ollama_service.embed_many([item["text"] for item in batch])
        await asyncio.to_thread(qdrant_service.upsert_batch, vectors, batch, version)
    # Old vectors remain available for in-flight retrieval snapshots. Failed
    # versions stay invisible and can be garbage collected during maintenance.
    await asyncio.to_thread(index_manifest.publish, source, version, staged)
    logging.getLogger("ingestion").info("ingestion_published version=%s chunks=%d duration_ms=%d",
        version, len(staged), (time.monotonic() - started) * 1000)
    return staged
