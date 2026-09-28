from fastapi import APIRouter, HTTPException
import asyncio
from app.services.ingestion_service import ingest
from app.services.chunking_service import chunk_text

from app.schemas.knowledge import (
    KnowledgeCreateRequest,
    KnowledgeCreateResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.dedup_service import compute_text_hash
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


router = APIRouter()


@router.post("/knowledge", response_model=KnowledgeCreateResponse)
async def create_knowledge(payload: KnowledgeCreateRequest):
    try:
        content_hash = compute_text_hash(payload.text, payload.source_name)

        existing = await asyncio.to_thread(qdrant_service.get_sample_by_content_hash, content_hash)
        if existing:

            return KnowledgeCreateResponse(
                id=(existing or {}).get("id", ""),
                text=payload.text,
                source_name=payload.source_name,
                content_hash=content_hash,
                skipped_duplicate=True,
                message="Knowledge identik sudah ter-index sebelumnya. Upload dilewati.",
            )

        records = await ingest(f"manual:{content_hash}", [
            {"text": chunk, "source_name": payload.source_name, "source_type": "manual",
             "content_hash": content_hash, "chunk_index": i}
            for i, chunk in enumerate(chunk_text(payload.text))
        ])
        point_id = records[0]["id"]

        return KnowledgeCreateResponse(
            id=point_id,
            text=payload.text,
            source_name=payload.source_name,
            content_hash=content_hash,
            skipped_duplicate=False,
            message="Knowledge berhasil di-index.",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menyimpan knowledge: {str(exc)}"
        )


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(payload: KnowledgeSearchRequest):
    try:
        query_vector = await ollama_service.embed(payload.query)

        results = await asyncio.to_thread(qdrant_service.search,
            query_vector=query_vector,
            top_k=payload.top_k,
        )

        return KnowledgeSearchResponse(results=results)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mencari knowledge: {str(exc)}"
        )
