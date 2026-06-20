from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.knowledge import router as knowledge_router
from app.api.documents import router as documents_router
from app.core.config import settings


app = FastAPI(
    title=settings.APP_NAME
)


app.include_router(
    health_router,
    prefix="/api",
    tags=["health"]
)

app.include_router(
    chat_router,
    prefix="/api",
    tags=["chat"]
)

app.include_router(
    knowledge_router,
    prefix="/api",
    tags=["knowledge"]
)

app.include_router(
    documents_router,
    prefix="/api",
    tags=["documents"]
)