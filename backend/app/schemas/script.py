"""Request and response models for script generation and editing."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScriptGenerateRequest(BaseModel):
    """Explicit opt-in is required before replacing an existing script."""

    regenerate: bool = False


class ScriptUpdateRequest(BaseModel):
    content: str = Field(..., min_length=50, max_length=100000)


class ScriptResponse(BaseModel):
    id: int
    creative_brief_id: int
    outline_id: int
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
