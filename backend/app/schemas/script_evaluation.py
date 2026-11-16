"""Validation and response models for script quality evaluations."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


Score = Annotated[int, Field(ge=1, le=5, strict=True)]


class CriterionEvaluation(BaseModel):
    score: Score
    explanation: str = Field(..., min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("explanation")
    @classmethod
    def explanation_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Explanation cannot be blank")
        return cleaned


class ScriptEvaluationCriteria(BaseModel):
    relevance_to_brief: CriterionEvaluation
    outline_alignment: CriterionEvaluation
    story_structure_and_coherence: CriterionEvaluation
    character_consistency: CriterionEvaluation
    dialogue_quality: CriterionEvaluation
    genre_and_format_compliance: CriterionEvaluation

    model_config = ConfigDict(extra="forbid")


class ScriptEvaluationContent(BaseModel):
    criteria: ScriptEvaluationCriteria
    summary: str = Field(..., min_length=1, max_length=2000)
    strengths: list[str] = Field(..., min_length=1, max_length=10)
    improvement_suggestions: list[str] = Field(..., min_length=1, max_length=10)

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary")
    @classmethod
    def summary_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Summary cannot be blank")
        return cleaned

    @field_validator("strengths", "improvement_suggestions")
    @classmethod
    def list_items_must_not_be_blank(cls, values: list[str]) -> list[str]:
        cleaned_values = [value.strip() for value in values]
        if any(not value for value in cleaned_values):
            raise ValueError("List items cannot be blank")
        return cleaned_values


class ScriptEvaluationResponse(BaseModel):
    id: int
    script_version_id: int
    criteria: ScriptEvaluationCriteria
    overall_score: float
    summary: str
    strengths: list[str]
    improvement_suggestions: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
