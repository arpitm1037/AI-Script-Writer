"""Generation and persistence for scripts based on approved outlines."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.outline import Outline
from app.db.models.script import Script
from app.db.models.creative_brief import CreativeBrief
from app.llm.base import LLMProvider
from app.prompts.script_prompt import build_script_prompt
from app.services.creative_brief_service import get_creative_brief


class InvalidScriptResponseError(Exception):
    """Raised when an LLM response is not usable script content."""


def _get_approved_outline(
    db: Session, brief_id: int, user_id: int
) -> tuple[CreativeBrief, Outline]:
    """Return an owned brief and its approved outline or raise an HTTP error."""
    brief = get_creative_brief(db, brief_id, user_id)
    outline = db.scalar(select(Outline).where(Outline.creative_brief_id == brief.id))
    if outline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outline not found")
    if not outline.is_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Outline must be approved before script generation",
        )
    return brief, outline


def _validate_script_response(response_text: str) -> str:
    """Reject empty or implausibly incomplete provider output before storage."""
    if not isinstance(response_text, str):
        raise InvalidScriptResponseError("LLM returned an invalid script")
    content = response_text.strip()
    if len(content) < 50:
        raise InvalidScriptResponseError("LLM returned an incomplete script")
    if len(content) > 100000:
        raise InvalidScriptResponseError("LLM returned an oversized script")
    return content


def generate_script(
    db: Session,
    brief_id: int,
    user_id: int,
    provider: LLMProvider,
    *,
    regenerate: bool,
) -> tuple[Script, bool]:
    """Generate a script from an approved outline without altering that outline."""
    brief, outline = _get_approved_outline(db, brief_id, user_id)
    existing = db.scalar(select(Script).where(Script.creative_brief_id == brief.id))
    if existing is not None and not regenerate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A script already exists; set regenerate=true to replace it",
        )

    prompt = build_script_prompt(brief, outline)
    content = _validate_script_response(
        provider.generate(
            system_instructions=prompt.system_instructions,
            user_content=prompt.user_content,
        )
    )

    if existing is None:
        script = Script(
            creative_brief_id=brief.id,
            outline_id=outline.id,
            content=content,
        )
        db.add(script)
        created = True
    else:
        script = existing
        created = False

    # Imported lazily to avoid a module cycle; every current script has a
    # baseline version, and explicit regeneration appends rather than erases.
    from app.services.script_version_service import _append_version, ensure_initial_version

    if created:
        db.flush()
        ensure_initial_version(db, script)
    else:
        _append_version(db, script, content, "Script regenerated")
    if created:
        script.content = content

    db.commit()
    db.refresh(script)
    return script, created


def get_script(db: Session, brief_id: int, user_id: int) -> Script:
    """Return the script for an owned brief, or 404 when it does not exist."""
    brief = get_creative_brief(db, brief_id, user_id)
    script = db.scalar(select(Script).where(Script.creative_brief_id == brief.id))
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return script


def update_script(db: Session, brief_id: int, user_id: int, content: str) -> Script:
    """Append a manual edit to version history and update the current script."""
    script = get_script(db, brief_id, user_id)
    cleaned_content = content.strip()
    if len(cleaned_content) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Script content is too short",
        )
    from app.services.script_version_service import _append_version

    _append_version(db, script, cleaned_content, "Manual script edit")
    db.commit()
    db.refresh(script)
    return script
