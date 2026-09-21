from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin

MISTAKE_TYPES = (
    "conceptual",
    "calculation",
    "formula",
    "reasoning",
    "misreading",
    "carelessness",
    "time_management",
    "vocabulary",
    "question_interpretation",
    "command_word",
    "evidence",
    "accuracy",
)


class MistakePattern(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "mistake_pattern"
    __table_args__ = (
        UniqueConstraint("student_id", "objective_id", "mistake_type", "fingerprint"),
        CheckConstraint("severity in ('low','medium','high')", name="severity"),
        CheckConstraint("status in ('open','improving','resolved')", name="status"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("topic.id"))
    objective_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_objective.id"))
    mistake_type: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    occurrences: Mapped[int] = mapped_column(SmallInteger, default=1)
    severity: Mapped[str] = mapped_column(String(8))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clean_streak: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="open")
    resolution: Mapped[str | None] = mapped_column(Text)


class MistakeOccurrence(IdMixin, StudentScoped, Base):
    __tablename__ = "mistake_occurrence"
    pattern_id: Mapped[UUID] = mapped_column(ForeignKey("mistake_pattern.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempt.id", ondelete="CASCADE"))
    evaluation_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.id", ondelete="CASCADE"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
