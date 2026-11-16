"""Persistence and response validation for Creative Brief outlines."""

import json

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.outline import Outline
from app.llm.base import LLMProvider
from app.prompts.outline_prompt import build_outline_prompt
from app.schemas.outline import OutlineContent
from app.services.creative_brief_service import get_creative_brief


class InvalidOutlineResponseError(Exception):
    """Raised when an LLM response cannot be safely stored as an outline."""


def _get_outline_for_owned_brief(db: Session, brief_id: int, user_id: int) -> Outline:
    """Return an outline only after confirming ownership of its source brief."""
    brief = get_creative_brief(db, brief_id, user_id)
    outline = db.scalar(select(Outline).where(Outline.creative_brief_id == brief.id))
    if outline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outline not found")
    return outline


def parse_outline_response(response_text: str) -> OutlineContent:
    """Validate JSON-only LLM output before it is persisted."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        return OutlineContent.model_validate(data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise InvalidOutlineResponseError("LLM returned an invalid outline") from exc


def generate_outline(
    db: Session,
    brief_id: int,
    user_id: int,
    provider: LLMProvider,
    *,
    regenerate: bool,
) -> tuple[Outline, bool]:
    """Generate and persist an outline; approved outlines are never overwritten."""
    brief = get_creative_brief(db, brief_id, user_id)
    existing = db.scalar(select(Outline).where(Outline.creative_brief_id == brief.id))
    if existing is not None:
        if existing.is_approved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approved outlines cannot be regenerated",
            )
        if not regenerate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An outline already exists; set regenerate=true to replace it",
            )

    prompt = build_outline_prompt(brief)
    generated = provider.generate(
        system_instructions=prompt.system_instructions,
        user_content=prompt.user_content,
    )
    content = parse_outline_response(generated)

    if existing is None:
        outline = Outline(creative_brief_id=brief.id, content=content.model_dump())
        db.add(outline)
        created = True
    else:
        existing.content = content.model_dump()
        outline = existing
        created = False

    db.commit()
    db.refresh(outline)
    return outline, created


def get_outline(db: Session, brief_id: int, user_id: int) -> Outline:
    return _get_outline_for_owned_brief(db, brief_id, user_id)


def update_outline(
    db: Session, brief_id: int, user_id: int, content: OutlineContent
) -> Outline:
    outline = _get_outline_for_owned_brief(db, brief_id, user_id)
    if outline.is_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approved outlines cannot be edited",
        )
    outline.content = content.model_dump()
    db.commit()
    db.refresh(outline)
    return outline


def approve_outline(db: Session, brief_id: int, user_id: int) -> Outline:
    outline = _get_outline_for_owned_brief(db, brief_id, user_id)
    if outline.is_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Outline is already approved",
        )
    outline.is_approved = True
    db.commit()
    db.refresh(outline)
    return outline
