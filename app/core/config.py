from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Local RAG MVP"
    APP_ENV: str = "local"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
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
