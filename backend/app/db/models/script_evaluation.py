"""SQLAlchemy model for quality evaluations of script versions."""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScriptEvaluation(Base):
    """An immutable quality evaluation of one script version."""

    __tablename__ = "script_evaluations"
    __table_args__ = (
        CheckConstraint(
            "overall_score >= 1 AND overall_score <= 5",
            name="ck_script_evaluation_overall_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    script_version_id: Mapped[int] = mapped_column(
        ForeignKey("script_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    criteria: Mapped[dict[str, dict[str, int | str]]] = mapped_column(
        JSON, nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    improvement_suggestions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    script_version: Mapped["ScriptVersion"] = relationship(back_populates="evaluations")
