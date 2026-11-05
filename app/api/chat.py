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
from app.services.rag_service import answer_with_rag, greeting_response
from app.services.rag_errors import RagDependencyError
from app.services.ai_service import AIProviderError
from app.services.model_service import chat_model_context, list_chat_models


router = APIRouter()


@router.get("/llm/models")
async def chat_models():
    return await list_chat_models()


async def select_model(model: str | None):
    if model is not None:
        catalog = await list_chat_models()
        if model not in catalog["models"]:
            raise HTTPException(status_code=422, detail="Model tidak tersedia untuk Chat Completions. Muat ulang daftar model.")
    return chat_model_context.set(model)


@router.post("/chat-basic", response_model=ChatBasicResponse)
async def chat_basic(payload: ChatBasicRequest):
    token = await select_model(payload.model)
    try:
        answer = await ollama_service.generate(payload.message)
        return ChatBasicResponse(answer=answer)

    except AIProviderError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memanggil Ollama: {str(exc)}"
        )
    finally:
        chat_model_context.reset(token)


@router.post("/embedding-test", response_model=EmbeddingTestResponse)
async def embedding_test(payload: EmbeddingTestRequest):
    try:
        vector = await ollama_service.embed(payload.text)

        return EmbeddingTestResponse(
            dimension=len(vector),
            sample=vector[:10],
        )

    except AIProviderError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membuat embedding: {str(exc)}"
        )


@router.post("/chat-rag", response_model=ChatRagResponse)
async def chat_rag(payload: ChatRagRequest):
    greeting = greeting_response(payload.question)
    if greeting:
        return ChatRagResponse(answer=greeting, sources=[], status="greeting")
    token = await select_model(payload.model)
    try:
        result = await answer_with_rag(
            question=payload.question,
            top_k=payload.top_k,
        )

        return ChatRagResponse(**result)

    except (AIProviderError, RagDependencyError):
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menjalankan RAG chat: {str(exc)}"
        )
    finally:
        chat_model_context.reset(token)
