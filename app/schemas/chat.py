from pydantic import BaseModel, Field

class ChatBasicRequest(BaseModel):
    message: str = Field(..., min_length=1)

class ChatBasicResponse(BaseModel):
    answer: str