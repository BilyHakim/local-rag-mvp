from fastapi import APIRouter, HTTPException

from app.schemas.knowledge import (
    KnowledgeCreateRequest,
    KnowledgeCreateResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.dedup_service import compute_text_hash, knowledge_point_id
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


router = APIRouter()


@router.post("/knowledge", response_model=KnowledgeCreateResponse)
async def create_knowledge(payload: KnowledgeCreateRequest):
    try:
        content_hash = compute_text_hash(payload.text, payload.source_name)

        if qdrant_service.exists_by_content_hash(content_hash):
            existing = qdrant_service.get_sample_by_content_hash(content_hash)

            return KnowledgeCreateResponse(
                id=(existing or {}).get("id", ""),
                text=payload.text,
                source_name=payload.source_name,
                content_hash=content_hash,
                skipped_duplicate=True,
                message="Knowledge identik sudah ter-index sebelumnya. Upload dilewati.",
            )

        vector = await ollama_service.embed(payload.text)
        point_id = knowledge_point_id(content_hash)

        qdrant_service.upsert_text(
            vector=vector,
            text=payload.text,
            source_name=payload.source_name,
            metadata={
                "source_type": "manual",
                "content_hash": content_hash,
            },
            point_id=point_id,
        )

        return KnowledgeCreateResponse(
            id=point_id,
            text=payload.text,
            source_name=payload.source_name,
            vector_dimension=len(vector),
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

        results = qdrant_service.search(
            query_vector=query_vector,
            top_k=payload.top_k,
        )

        return KnowledgeSearchResponse(results=results)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mencari knowledge: {str(exc)}"
        )
