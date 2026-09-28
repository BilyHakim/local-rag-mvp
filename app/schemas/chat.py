from pydantic import BaseModel, Field


class ChatBasicRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatBasicResponse(BaseModel):
    answer: str


class EmbeddingTestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000)


class EmbeddingTestResponse(BaseModel):
    dimension: int
    sample: list[float]


class ChatRagRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatRagSource(BaseModel):
    id: str
    score: float
    text: str
    source_name: str | None = None
    source_type: str | None = None
    filename: str | None = None
    page_number: int | None = None
    chunk_index: int | None = None
    file_format: str | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    database: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    row_key: str | None = None


class Citation(BaseModel):
    source_id: str
    evidence_text: str
    filename: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    table_name: str | None = None
    row_key: str | None = None


class ChatRagResponse(BaseModel):
    answer: str
    sources: list[ChatRagSource]
    citations: list[Citation] = Field(default_factory=list)
    status: str = "answered"
