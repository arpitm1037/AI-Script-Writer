"""SQLAlchemy model for the structured outline attached to a creative brief."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Outline(Base):
    """The current generated outline for a creative brief."""

    __tablename__ = "outlines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    creative_brief_id: Mapped[int] = mapped_column(
        ForeignKey("creative_briefs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creative_brief: Mapped["CreativeBrief"] = relationship(back_populates="outline")
    script: Mapped["Script | None"] = relationship(
        back_populates="outline",
        cascade="all, delete-orphan",
        uselist=False,
    )
