from pydantic import BaseModel, Field


class ChatBasicRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatBasicResponse(BaseModel):
    answer: str


class EmbeddingTestRequest(BaseModel):
    text: str = Field(..., min_length=1)


class EmbeddingTestResponse(BaseModel):
    dimension: int
    sample: list[float]


class ChatRagRequest(BaseModel):
    question: str = Field(..., min_length=2)
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


class ChatRagResponse(BaseModel):
    answer: str
    sources: list[ChatRagSource]