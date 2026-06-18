from fastapi import APIRouter, HTTPException

from app.schemas.chat import (
    ChatBasicRequest,
    ChatBasicResponse,
    EmbeddingTestRequest,
    EmbeddingTestResponse,
    ChatRagRequest,
    ChatRagResponse,
)
from app.services.ollama_service import ollama_service
from app.services.rag_service import answer_with_rag


router = APIRouter()


@router.post("/chat-basic", response_model=ChatBasicResponse)
async def chat_basic(payload: ChatBasicRequest):
    try:
        answer = await ollama_service.generate(payload.message)
        return ChatBasicResponse(answer=answer)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memanggil Ollama: {str(exc)}"
        )


@router.post("/embedding-test", response_model=EmbeddingTestResponse)
async def embedding_test(payload: EmbeddingTestRequest):
    try:
        vector = await ollama_service.embed(payload.text)

        return EmbeddingTestResponse(
            dimension=len(vector),
            sample=vector[:10],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membuat embedding: {str(exc)}"
        )


@router.post("/chat-rag", response_model=ChatRagResponse)
async def chat_rag(payload: ChatRagRequest):
    try:
        result = await answer_with_rag(
            question=payload.question,
            top_k=payload.top_k,
        )

        return ChatRagResponse(**result)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menjalankan RAG chat: {str(exc)}"
        )