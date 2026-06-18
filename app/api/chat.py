from fastapi import APIRouter, HTTPException

from app.schemas.chat import (
    ChatBasicRequest,
    ChatBasicResponse,
    EmbeddingTestRequest,
    EmbeddingTestResponse,
)
from app.services.ollama_service import ollama_service


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