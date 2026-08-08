from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.knowledge import router as knowledge_router
from app.api.documents import router as documents_router
from app.api.postgres import router as postgres_router
from app.core.config import settings


app = FastAPI(
    title=settings.APP_NAME
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def web_app():
    return FileResponse(static_dir / "index.html")


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

app.include_router(
    postgres_router,
    prefix="/api",
    tags=["postgres"]
)
