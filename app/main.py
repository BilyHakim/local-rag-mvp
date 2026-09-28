from pathlib import Path
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.knowledge import router as knowledge_router
from app.api.documents import router as documents_router
from app.api.postgres import router as postgres_router
from app.core.config import settings
from app.core.middleware import SecurityMiddleware
from app.services.ollama_service import ollama_service
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    yield
    await ollama_service.close()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV == "local" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.APP_ENV == "local" else None,
)
app.add_middleware(SecurityMiddleware)


@app.exception_handler(HTTPException)
async def sanitized_error(request, exc):
    if exc.status_code >= 500:
        cause = exc.__cause__ or exc.__context__ or exc
        logging.getLogger("http").error("api_error status=%d error_type=%s", exc.status_code, type(cause).__name__)
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": "Layanan belum dapat memproses request" if exc.status_code >= 500 else exc.detail})

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
