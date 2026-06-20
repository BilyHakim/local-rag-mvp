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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()
