"""Validation models for generated and user-edited script outlines."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OutlineAct(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=1, max_length=5000)
    beats: list[str] = Field(..., min_length=1, max_length=20)


class OutlineContent(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    logline: str = Field(..., min_length=1, max_length=2000)
    acts: list[OutlineAct] = Field(..., min_length=3, max_length=5)

    model_config = ConfigDict(extra="forbid")


class OutlineGenerateRequest(BaseModel):
    """Explicit opt-in is required before replacing an unapproved outline."""

    regenerate: bool = False


class OutlineUpdateRequest(BaseModel):
    content: OutlineContent


class OutlineResponse(BaseModel):
    id: int
    creative_brief_id: int
    content: OutlineContent
    is_approved: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
