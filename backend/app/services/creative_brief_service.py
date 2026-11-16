"""Create, retrieve, update, and delete user-owned creative briefs."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.creative_brief import CreativeBrief


def _get_owned_brief(db: Session, brief_id: int, user_id: int) -> CreativeBrief:
    """Fetch a brief that belongs to the given user. 404 otherwise.

    Filtering by user_id makes "doesn't exist" and "belongs to someone else"
    indistinguishable, so cross-user access is never revealed.
    """
    brief = db.scalar(
        select(CreativeBrief).where(
            CreativeBrief.id == brief_id, CreativeBrief.user_id == user_id
        )
    )
    if brief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creative brief not found",
        )
    return brief


def create_creative_brief(db: Session, user_id: int, data: dict) -> CreativeBrief:
    """Create and persist a creative brief owned by user_id."""
    brief = CreativeBrief(user_id=user_id, **data)
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def list_user_briefs(db: Session, user_id: int) -> list[CreativeBrief]:
    """Return all briefs belonging to user_id, newest first."""
    return list(
        db.scalars(
            select(CreativeBrief)
            .where(CreativeBrief.user_id == user_id)
            .order_by(CreativeBrief.created_at.desc())
        )
    )


def get_creative_brief(db: Session, brief_id: int, user_id: int) -> CreativeBrief:
    """Return a single brief owned by user_id."""
    return _get_owned_brief(db, brief_id, user_id)


def update_creative_brief(
    db: Session, brief_id: int, user_id: int, data: dict
) -> CreativeBrief:
    """Update a brief owned by user_id with the given field values."""
    brief = _get_owned_brief(db, brief_id, user_id)
    for field, value in data.items():
        setattr(brief, field, value)
    db.commit()
    db.refresh(brief)
    return brief


def delete_creative_brief(db: Session, brief_id: int, user_id: int) -> CreativeBrief:
    """Delete a brief owned by user_id and return the removed record."""
    brief = _get_owned_brief(db, brief_id, user_id)
    db.delete(brief)
    db.commit()
    return brief