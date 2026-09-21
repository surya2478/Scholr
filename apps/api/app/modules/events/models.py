"""The append-only learning event log. (Sessions and conversations live in the tutoring module.)"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped

EVENT_TYPES = (
    "session_started",
    "session_ended",
    "explanation_viewed",
    "attempt_submitted",
    "attempt_evaluated",
    "evaluation_overridden",
    "help_requested",
    "help_given",
    "self_explanation_given",
    "confidence_reported",
    "mistake_diagnosed",
    "mistake_resolved",
    "school_result_recorded",
    "external_training_logged",
    "plan_item_completed",
    "plan_item_skipped",
)


class LearningEvent(IdMixin, StudentScoped, Base):
    """Append-only source of truth. UPDATE/DELETE are rejected by a database trigger (AC-A4)."""

    __tablename__ = "learning_event"
    __table_args__ = (Index("ix_learning_event_student_time", "student_id", "occurred_at"),)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    type: Mapped[str] = mapped_column(String(48), index=True)
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("subject.id"))
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    schema_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
