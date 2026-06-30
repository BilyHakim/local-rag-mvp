from pydantic import BaseModel, Field


class KnowledgeCreateRequest(BaseModel):
    text: str = Field(..., min_length=3)
    source_name: str | None = None


class KnowledgeCreateResponse(BaseModel):
    id: str
    text: str
    source_name: str | None = None
    vector_dimension: int | None = None
    content_hash: str | None = None
    skipped_duplicate: bool = False
    message: str | None = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchItem(BaseModel):
    id: str
    score: float
    text: str
    source_name: str | None = None
    source_type: str | None = None
    filename: str | None = None
    page_number: int | None = None
    chunk_index: int | None = None


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchItem]