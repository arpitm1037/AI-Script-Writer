"""Request and response models for creative-brief endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreativeBriefCreate(BaseModel):
    """Payload for POST /api/v1/creative-briefs.

    Semantic validation (allowed genres, non-empty text, etc.) lives in
    app/validators/creative_brief.py.
    """

    topic: str = Field(..., min_length=1, max_length=2000)
    genre: str = Field(..., min_length=1, max_length=50)
    output_format: str = Field(..., min_length=1, max_length=60)
    language: str = Field(..., min_length=1, max_length=60)
    tone: str = Field(..., min_length=1, max_length=200)
    target_audience: str = Field(..., min_length=1, max_length=200)
    duration: str = Field(..., min_length=1, max_length=100)
    characters: str = Field(..., min_length=1, max_length=2000)
    setting: str = Field(..., min_length=1, max_length=1000)
    key_points: str = Field(..., min_length=1, max_length=2000)
    detail_level: str = Field(..., min_length=1, max_length=30)
    special_instructions: str | None = Field(default=None, max_length=5000)


class CreativeBriefUpdate(BaseModel):
    """Payload for PATCH /api/v1/creative-briefs/{brief_id}.

    Every field is optional; only the provided fields are updated.
    """

    topic: str | None = Field(default=None, min_length=1, max_length=2000)
    genre: str | None = Field(default=None, min_length=1, max_length=50)
    output_format: str | None = Field(default=None, min_length=1, max_length=60)
    language: str | None = Field(default=None, min_length=1, max_length=60)
    tone: str | None = Field(default=None, min_length=1, max_length=200)
    target_audience: str | None = Field(default=None, min_length=1, max_length=200)
    duration: str | None = Field(default=None, min_length=1, max_length=100)
    characters: str | None = Field(default=None, min_length=1, max_length=2000)
    setting: str | None = Field(default=None, min_length=1, max_length=1000)
    key_points: str | None = Field(default=None, min_length=1, max_length=2000)
    detail_level: str | None = Field(default=None, min_length=1, max_length=30)
    special_instructions: str | None = Field(default=None, max_length=5000)


class CreativeBriefResponse(BaseModel):
    """A saved creative brief. Never exposes internal/ORM-only fields."""

    id: int
    user_id: int
    topic: str
    genre: str
    output_format: str
    language: str
    tone: str
    target_audience: str
    duration: str
    characters: str
    setting: str
    key_points: str
    detail_level: str
    special_instructions: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)