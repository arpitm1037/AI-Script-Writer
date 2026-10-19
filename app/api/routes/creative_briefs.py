from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.base import get_db
from app.db.models.creative_brief import CreativeBrief
from app.db.models.user import User
from app.schemas.creative_brief import (
    CreativeBriefCreate,
    CreativeBriefResponse,
    CreativeBriefUpdate,
)
from app.services import creative_brief_service
from app.validators import creative_brief as brief_validator

router = APIRouter(prefix="/api/v1/creative-briefs", tags=["Creative Briefs"])


# Creative Brief APIs
@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreativeBriefResponse)
def create_brief(
    payload: CreativeBriefCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBrief:
    """Create a creative brief owned by the authenticated user."""
    data = brief_validator.validate_create(payload.model_dump())
    return creative_brief_service.create_creative_brief(db, current_user.id, data)


@router.get("", response_model=list[CreativeBriefResponse])
def list_briefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CreativeBrief]:
    """List the authenticated user's creative briefs."""
    return creative_brief_service.list_user_briefs(db, current_user.id)


@router.get("/{brief_id}", response_model=CreativeBriefResponse)
def get_brief(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBrief:
    """Get one of the authenticated user's creative briefs."""
    return creative_brief_service.get_creative_brief(db, brief_id, current_user.id)


@router.patch("/{brief_id}", response_model=CreativeBriefResponse)
def update_brief(
    brief_id: int,
    payload: CreativeBriefUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreativeBrief:
    """Update one of the authenticated user's creative briefs."""
    data = brief_validator.validate_update(
        payload.model_dump(exclude_unset=True, exclude_none=True)
    )
    return creative_brief_service.update_creative_brief(db, brief_id, current_user.id, data)


@router.delete("/{brief_id}")
def delete_brief(
    brief_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete one of the authenticated user's creative briefs."""
    creative_brief_service.delete_creative_brief(db, brief_id, current_user.id)
    return {"message": "Creative brief deleted"}