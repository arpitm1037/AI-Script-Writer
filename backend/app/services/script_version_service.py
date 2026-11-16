"""Append-only script revision and version-history operations."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.outline import Outline
from app.db.models.script import Script
from app.db.models.script_version import ScriptVersion
from app.llm.base import LLMProvider
from app.prompts.revision_prompt import build_revision_prompt
from app.services.script_service import _validate_script_response, get_script


def _latest_version(db: Session, script_id: int) -> ScriptVersion | None:
    """Return the most recently numbered version, if one exists."""
    return db.scalar(
        select(ScriptVersion)
        .where(ScriptVersion.script_id == script_id)
        .order_by(ScriptVersion.version_number.desc())
    )


def ensure_initial_version(db: Session, script: Script) -> ScriptVersion:
    """Backfill version 1 for scripts created before Phase 8 when necessary."""
    latest = _latest_version(db, script.id)
    if latest is not None:
        script.content = latest.content
        return latest
    initial = ScriptVersion(
        script_id=script.id,
        version_number=1,
        content=script.content,
        revision_instructions=None,
    )
    db.add(initial)
    db.flush()
    return initial


def _append_version(
    db: Session, script: Script, content: str, revision_instructions: str | None
) -> ScriptVersion:
    """Append the next version and make its content current on the script."""
    latest = ensure_initial_version(db, script)
    version = ScriptVersion(
        script_id=script.id,
        version_number=latest.version_number + 1,
        content=content,
        revision_instructions=revision_instructions,
    )
    db.add(version)
    script.content = content
    db.flush()
    return version


def revise_script(
    db: Session,
    brief_id: int,
    user_id: int,
    provider: LLMProvider,
    revision_instructions: str,
) -> ScriptVersion:
    """Generate a new version and reject stale concurrent revisions."""
    instructions = revision_instructions.strip()
    if not instructions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Revision instructions cannot be empty",
        )

    script = get_script(db, brief_id, user_id)
    outline = db.get(Outline, script.outline_id)
    if outline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outline not found")

    baseline = _latest_version(db, script.id)
    base_version_number = baseline.version_number if baseline is not None else 0
    baseline_content = baseline.content if baseline is not None else script.content
    script.content = baseline_content
    prompt = build_revision_prompt(script.creative_brief, outline, script, instructions)
    # Release the read transaction while Gemini runs; only persist after a
    # successful response and a fresh concurrency check.
    db.commit()
    content = _validate_script_response(
        provider.generate(
            system_instructions=prompt.system_instructions,
            user_content=prompt.user_content,
        )
    )

    locked_script = db.scalar(select(Script).where(Script.id == script.id).with_for_update())
    if locked_script is None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    latest = _latest_version(db, locked_script.id)
    latest_version_number = latest.version_number if latest is not None else 0
    if (
        latest_version_number != base_version_number
        or (latest is None and locked_script.content != baseline_content)
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Script changed during revision; retrieve the latest version and try again",
        )
    try:
        if latest is None:
            ensure_initial_version(db, locked_script)
        version = _append_version(db, locked_script, content, instructions)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Script changed during revision; retrieve the latest version and try again",
        ) from exc
    db.refresh(version)
    return version


def list_versions(db: Session, brief_id: int, user_id: int) -> list[ScriptVersion]:
    """Return all versions for an owned script in ascending order."""
    script = get_script(db, brief_id, user_id)
    ensure_initial_version(db, script)
    db.commit()
    return list(
        db.scalars(
            select(ScriptVersion)
            .where(ScriptVersion.script_id == script.id)
            .order_by(ScriptVersion.version_number)
        )
    )


def get_version(
    db: Session, brief_id: int, user_id: int, version_number: int
) -> ScriptVersion:
    """Return one version of an owned script or raise 404."""
    script = get_script(db, brief_id, user_id)
    ensure_initial_version(db, script)
    db.commit()
    version = db.scalar(
        select(ScriptVersion).where(
            ScriptVersion.script_id == script.id,
            ScriptVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script version not found")
    return version


def restore_version(
    db: Session, brief_id: int, user_id: int, version_number: int
) -> ScriptVersion:
    """Make an old version current by appending, never modifying, history."""
    script = get_script(db, brief_id, user_id)
    target = get_version(db, brief_id, user_id, version_number)
    locked_script = db.scalar(select(Script).where(Script.id == script.id).with_for_update())
    version = _append_version(
        db,
        locked_script,
        target.content,
        f"Restored version {target.version_number}",
    )
    db.commit()
    db.refresh(version)
    return version
