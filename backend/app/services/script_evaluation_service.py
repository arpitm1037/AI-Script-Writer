"""Evaluation and history operations for immutable script versions."""

import json

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.outline import Outline
from app.db.models.script import Script
from app.db.models.script_evaluation import ScriptEvaluation
from app.db.models.script_version import ScriptVersion
from app.llm.base import LLMProvider
from app.prompts.evaluation_prompt import build_evaluation_prompt
from app.schemas.script_evaluation import ScriptEvaluationContent
from app.services.creative_brief_service import get_creative_brief


class InvalidEvaluationResponseError(Exception):
    """Raised when an LLM response is malformed or incomplete."""


def parse_evaluation_response(response_text: str) -> ScriptEvaluationContent:
    """Parse and strictly validate a Gemini evaluation response."""
    if not isinstance(response_text, str):
        raise InvalidEvaluationResponseError("LLM returned an invalid evaluation")

    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return ScriptEvaluationContent.model_validate(json.loads(text))
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidEvaluationResponseError("LLM returned an invalid evaluation") from exc


def get_owned_script_version(
    db: Session, brief_id: int, version_number: int, user_id: int
) -> tuple[Script, ScriptVersion, Outline]:
    """Resolve a version only through the authenticated user's owned brief."""
    brief = get_creative_brief(db, brief_id, user_id)
    script = db.scalar(
        select(Script).where(Script.creative_brief_id == brief.id)
    )
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Script not found"
        )

    version = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.script_id == script.id,
            ScriptVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Script version not found"
        )

    outline = db.get(Outline, script.outline_id)
    if outline is None or not outline.is_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An approved outline is required to evaluate a script",
        )
    return script, version, outline


def evaluate_script_version(
    db: Session,
    brief_id: int,
    version_number: int,
    user_id: int,
    provider: LLMProvider,
) -> ScriptEvaluation:
    """Generate, validate, and persist a new evaluation for the selected version."""
    script, version, outline = get_owned_script_version(
        db, brief_id, version_number, user_id
    )
    prompt = build_evaluation_prompt(script.creative_brief, outline, version)
    generated = provider.generate(
        system_instructions=prompt.system_instructions,
        user_content=prompt.user_content,
    )
    evaluation_content = parse_evaluation_response(generated)
    scores = [
        getattr(evaluation_content.criteria, name).score
        for name in (
            "relevance_to_brief",
            "outline_alignment",
            "story_structure_and_coherence",
            "character_consistency",
            "dialogue_quality",
            "genre_and_format_compliance",
        )
    ]
    overall_score = round(sum(scores) / len(scores), 2)

    evaluation = ScriptEvaluation(
        script_version_id=version.id,
        criteria=evaluation_content.criteria.model_dump(),
        overall_score=overall_score,
        summary=evaluation_content.summary,
        strengths=evaluation_content.strengths,
        improvement_suggestions=evaluation_content.improvement_suggestions,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def list_version_evaluations(
    db: Session, brief_id: int, version_number: int, user_id: int
) -> list[ScriptEvaluation]:
    """Return saved evaluations for an owned version, newest first."""
    _, version, _ = get_owned_script_version(db, brief_id, version_number, user_id)
    return list(
        db.scalars(
            select(ScriptEvaluation)
            .where(ScriptEvaluation.script_version_id == version.id)
            .order_by(ScriptEvaluation.created_at.desc(), ScriptEvaluation.id.desc())
        )
    )


def get_version_evaluation(
    db: Session,
    brief_id: int,
    version_number: int,
    evaluation_id: int,
    user_id: int,
) -> ScriptEvaluation:
    """Return an evaluation only when it belongs to the requested version."""
    _, version, _ = get_owned_script_version(db, brief_id, version_number, user_id)
    evaluation = db.scalar(
        select(ScriptEvaluation).where(
            ScriptEvaluation.script_version_id == version.id,
            ScriptEvaluation.id == evaluation_id,
        )
    )
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script evaluation not found",
        )
    return evaluation
