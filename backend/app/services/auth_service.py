"""Database operations for registration and credential authentication."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the user with the given email, or None."""
    return db.scalar(select(User).where(User.email == email))


def create_user(db: Session, name: str, email: str, password: str) -> User:
    """Create and persist a new user. Raises 409 if the email is already taken."""
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Verify credentials. Returns the user on success, None on failure."""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user