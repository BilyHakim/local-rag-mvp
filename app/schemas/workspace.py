from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class BrandProfile(BaseModel):
    name: str = Field(default="", max_length=160)
    description: str = Field(default="", max_length=6000)
    audience: str = Field(default="", max_length=2000)
    tone: str = Field(default="Profesional, jelas, bahasa Indonesia", max_length=1000)
    products: str = Field(default="", max_length=4000)
    guidelines: str = Field(default="", max_length=4000)
    cta: str = Field(default="", max_length=1000)
    visual_style: str = Field(default="", max_length=2000)


class Finding(BaseModel):
    priority: Literal["high", "medium", "low"]
    issue: str = Field(max_length=500)
    evidence: str = Field(max_length=2000)
    recommendation: str = Field(max_length=2000)


class SEOAnalysis(BaseModel):
    summary: str = Field(max_length=6000)
    recommendations: list[str] = Field(max_length=15)
    suggested_title: str = Field(max_length=300)
    suggested_description: str = Field(max_length=600)


class AuditRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    goal: str = Field(default="", max_length=3000)
    use_knowledge: bool = True


class SocialDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(min_length=1, max_length=12000)
    image_prompt: str = Field(min_length=1, max_length=4000)
    hashtags: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=3000)


class GenerateRequest(BaseModel):
    brief: str = Field(min_length=3, max_length=8000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    channel: Literal["instagram", "website"] = "instagram"
    use_knowledge: bool = True
    post_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    revision: int | None = Field(default=None, ge=1)


class PostEdit(BaseModel):
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(min_length=1, max_length=12000)
    image_prompt: str = Field(default="", max_length=4000)
    hashtags: list[str] = Field(default_factory=list, max_length=20)


class ManualPostRequest(BaseModel):
    channel: Literal["instagram", "website"] = "instagram"
    title: str = Field(default="Draft baru", min_length=1, max_length=200)
    caption: str = Field(default="", max_length=12000)


class RevisionRequest(BaseModel):
    revision: int = Field(ge=1)


class CampaignRequest(BaseModel):
    theme: str = Field(min_length=3, max_length=8000)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    channel: Literal["instagram", "website"] = "instagram"
    image_mode: Literal["manual", "automatic"] = "manual"
    use_knowledge: bool = True
    first_publish_at: datetime
    interval_hours: int = Field(default=24, ge=1, le=720)
    count: int = Field(default=7, ge=1, le=30)

    @field_validator("first_publish_at")
    @classmethod
    def future_aware(cls, value):
        return ScheduleRequest.future_aware(value)


class ScheduleRequest(RevisionRequest):
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def future_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Jadwal harus menyertakan timezone")
        if value <= datetime.now(timezone.utc):
            raise ValueError("Jadwal harus di masa depan")
        return value.astimezone(timezone.utc)


class ResolveRequest(RevisionRequest):
    outcome: Literal["published", "not_published"]
    external_id: str = Field(default="", max_length=200)
    external_url: str = Field(default="", max_length=2000)

    @field_validator("external_url")
    @classmethod
    def valid_external_url(cls, value):
        if value and not value.startswith("https://"):
            raise ValueError("URL hasil publikasi harus HTTPS")
        return value
