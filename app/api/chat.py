from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatBasicRequest, ChatBasicResponse
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