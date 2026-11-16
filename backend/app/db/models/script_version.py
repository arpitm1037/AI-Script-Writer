"""SQLAlchemy model for append-only script version history."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScriptVersion(Base):
    """Immutable historical content for a script revision."""

    __tablename__ = "script_versions"
    __table_args__ = (
        UniqueConstraint("script_id", "version_number", name="uq_script_version_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    script_id: Mapped[int] = mapped_column(
        ForeignKey("scripts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    script: Mapped["Script"] = relationship(back_populates="versions")
    evaluations: Mapped[list["ScriptEvaluation"]] = relationship(
        back_populates="script_version",
        cascade="all, delete-orphan",
        order_by="ScriptEvaluation.created_at",
    )
