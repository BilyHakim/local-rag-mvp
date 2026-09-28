from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    APP_NAME: str = "Local RAG MVP"
    APP_ENV: str = "local"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    API_KEYS: dict[str, dict[str, str]] = {}
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    MAX_CHUNKS: int = 10000
    MAX_SOURCES_PER_TENANT: int = 1000
    EMBED_BATCH_SIZE: int = 16
    REQUEST_TIMEOUT: int = 180
    RATE_LIMIT_PER_MINUTE: int = 60
    QDRANT_API_KEY: str | None = None
    POSTGRES_ALLOWED_TABLES: list[str] = []

    @model_validator(mode="after")
    def validate_runtime(self):
        if not 0 <= self.CHUNK_OVERLAP < self.CHUNK_SIZE:
            raise ValueError("Require 0 <= CHUNK_OVERLAP < CHUNK_SIZE")
        for value in (self.MAX_UPLOAD_BYTES, self.MAX_CHUNKS, self.MAX_SOURCES_PER_TENANT, self.EMBED_BATCH_SIZE,
                      self.REQUEST_TIMEOUT, self.RATE_LIMIT_PER_MINUTE):
            if value <= 0:
                raise ValueError("Runtime limits must be positive")
        if self.APP_ENV != "local" and not self.API_KEYS:
            raise ValueError("API_KEYS required outside local mode")
        import re
        for key, principal in self.API_KEYS.items():
            if self.APP_ENV != "local" and key.startswith("REPLACE_"):
                raise ValueError("Replace example API keys before starting staging")
            if len(key) < 32 or principal.get("role") not in {"admin", "reader"}:
                raise ValueError("API keys need >=32 characters and admin/reader role")
            if not re.fullmatch(r"[a-z0-9_-]{1,48}", principal.get("tenant", "")):
                raise ValueError("Invalid tenant")
        return self
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:3b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "local_knowledge"
    
    RAG_SCORE_THRESHOLD: float = 0.45
    
    STORAGE_DIR: str = "storage"
    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 150
    
    OCR_ENABLED: bool = True
    OCR_LANG: str = "eng+ind"
    OCR_DPI: int = 200
    OCR_MIN_TEXT_LENGTH: int = 20
    TESSERACT_CMD: str | None = None
    TESSDATA_DIR: str | None = None

    POSTGRES_ENABLED: bool = False
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "seamon-local-ipc-db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SCHEMA: str = "public"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()
