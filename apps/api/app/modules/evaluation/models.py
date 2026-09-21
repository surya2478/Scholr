from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class Evaluation(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "evaluation"
    __table_args__ = (
        CheckConstraint("status in ('final','needs_review','overridden')", name="status"),
        CheckConstraint("confidence between 0 and 1", name="confidence"),
    )
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempt.id", ondelete="CASCADE"), index=True)
    pipeline: Mapped[str] = mapped_column(String(32))
    pipeline_version: Mapped[str] = mapped_column(String(32))
    rubric_version: Mapped[str | None] = mapped_column(String(32))
    marks_awarded: Mapped[float] = mapped_column()
    marks_available: Mapped[float] = mapped_column()
    criterion_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    level_band: Mapped[int | None] = mapped_column(SmallInteger)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    diagnosed_mistakes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    tool_results: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column()
    agreement: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
