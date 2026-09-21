from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, StudentScoped


class MasteryState(StudentScoped, Base):
    """Projection rebuilt from learning_event (AC-A3)."""

    __tablename__ = "mastery_state"
    __table_args__ = (
        CheckConstraint("level between 0 and 5", name="level"),
        CheckConstraint("retention_risk in ('none','medium','high')", name="retention_risk"),
    )
    student_id: Mapped[UUID] = mapped_column(ForeignKey("student.id", ondelete="CASCADE"), primary_key=True)
    objective_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_objective.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(SmallInteger)
    score: Mapped[float] = mapped_column(Float)
    mastery_confidence: Mapped[float] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(SmallInteger)
    independent_successes: Mapped[int] = mapped_column(SmallInteger)
    distinct_days: Mapped[int] = mapped_column(SmallInteger)
    last_demonstrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_risk: Mapped[str] = mapped_column(String(8))
    rule_version: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SkillProfile(StudentScoped, Base):
    __tablename__ = "skill_profile"
    student_id: Mapped[UUID] = mapped_column(ForeignKey("student.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skill.id", ondelete="CASCADE"), primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    score: Mapped[float] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(SmallInteger)
    rule_version: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
