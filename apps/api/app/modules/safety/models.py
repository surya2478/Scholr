from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class SafetyIncident(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "safety_incident"
    __table_args__ = (
        CheckConstraint("severity between 1 and 3", name="severity"),
        CheckConstraint("escalation_status in ('none','notified','acknowledged','resolved')", name="escalation"),
    )
    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("message.id", ondelete="SET NULL"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[int] = mapped_column(SmallInteger)
    rule_ids: Mapped[list[str]] = mapped_column(ARRAY(String(48)), default=list)
    classifier_output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    policy_version: Mapped[str] = mapped_column(String(32))
    action_taken: Mapped[str] = mapped_column(String(32))
    escalation_status: Mapped[str] = mapped_column(String(16), default="none")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
