from fastapi import APIRouter, HTTPException

from app.schemas.knowledge import (
    KnowledgeCreateRequest,
    KnowledgeCreateResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


router = APIRouter()


@router.post("/knowledge", response_model=KnowledgeCreateResponse)
async def create_knowledge(payload: KnowledgeCreateRequest):
    try:
        vector = await ollama_service.embed(payload.text)

        point_id = qdrant_service.upsert_text(
            vector=vector,
            text=payload.text,
            source_name=payload.source_name,
        )

        return KnowledgeCreateResponse(
            id=point_id,
            text=payload.text,
            source_name=payload.source_name,
            vector_dimension=len(vector),
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