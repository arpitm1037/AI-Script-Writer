"""Request and response models for script revisions and version history."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScriptRevisionRequest(BaseModel):
    revision_instructions: str = Field(..., min_length=1, max_length=2000)


class ScriptVersionResponse(BaseModel):
    id: int
    script_id: int
    version_number: int
    content: str
    revision_instructions: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
