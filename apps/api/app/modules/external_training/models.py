from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin

KINDS = ("class", "test", "homework", "practice")


class ExternalTrainingLog(IdMixin, TimestampMixin, StudentScoped, Base):
    """One session of learning that happened somewhere else — the IIT Foundation classes (docs/PHASE-3.md).

    Independent evidence, like ``school_result``: it records what the external programme covered and how it
    went. It never becomes mastery evidence — mastery means Scholr's own evaluated attempts, with a help
    level and an evaluator confidence attached, and a coaching-centre percentage has neither (AC-X3).
    """

    __tablename__ = "external_training_log"
    __table_args__ = (
        CheckConstraint("kind in ('class','test','homework','practice')", name="kind"),
        CheckConstraint("duration_min is null or duration_min between 0 and 720", name="duration"),
        CheckConstraint("max_score is null or max_score > 0", name="max_score"),
        CheckConstraint("score is null or score >= 0", name="score"),
        CheckConstraint(
            "questions_attempted is null or questions_missed is null or questions_missed <= questions_attempted",
            name="questions",
        ),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    duration_min: Mapped[int | None] = mapped_column(SmallInteger)
    # Lessons the session covered, and the subset she struggled with.
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    weak_objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    max_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    questions_attempted: Mapped[int | None] = mapped_column(SmallInteger)
    questions_missed: Mapped[int | None] = mapped_column(SmallInteger)
    # Short labels copied from the provider's report ("sign errors", "did not finish"), in the parent's words.
    weaknesses: Mapped[list[str]] = mapped_column(ARRAY(String(120)), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_role: Mapped[str] = mapped_column(String(16))
