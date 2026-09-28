from fastapi import APIRouter

from app.core.config import settings
import asyncio
from fastapi.responses import JSONResponse, PlainTextResponse
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service
from app.services import index_manifest
from app.services.pdf_service import check_ocr_ready
from app.core.middleware import metrics
from app.services.rag_service import rag_metrics

router = APIRouter()


@router.get("/ready")
async def ready():
    try:
        await asyncio.wait_for(asyncio.to_thread(qdrant_service.client.get_collections), 10)
        response = await ollama_service.client.get(f"{ollama_service.base_url}/api/tags", timeout=5)
        response.raise_for_status()
        names = {item["name"] for item in response.json().get("models", [])}
        for name in (ollama_service.chat_model, ollama_service.embedding_model):
            if name not in names and f"{name}:latest" not in names:
                raise ValueError("Required model missing")
        await asyncio.to_thread(index_manifest.versions)
        if not await asyncio.to_thread(check_ocr_ready):
            raise RuntimeError("OCR unavailable")
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    lines = [f"rag_http_{key}_total {value}" for key, value in metrics.items()]
    lines.extend(f"rag_answers_{key}_total {value}" for key, value in rag_metrics.items())
    return "\n".join(lines) + "\n"

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }
