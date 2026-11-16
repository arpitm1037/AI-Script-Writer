"""SQLAlchemy model for the current script generated from an approved outline."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Script(Base):
    """The current generated script for one approved outline."""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    creative_brief_id: Mapped[int] = mapped_column(
        ForeignKey("creative_briefs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    outline_id: Mapped[int] = mapped_column(
        ForeignKey("outlines.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creative_brief: Mapped["CreativeBrief"] = relationship(back_populates="script")
    outline: Mapped["Outline"] = relationship(back_populates="script")
    versions: Mapped[list["ScriptVersion"]] = relationship(
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="ScriptVersion.version_number",
    )
