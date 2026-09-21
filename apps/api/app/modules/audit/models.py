from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantScoped


class AuditLog(IdMixin, TenantScoped, Base):
    """Important actions. Never stores conversation content or answers."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    actor_role: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    student_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))  # subject of the action, no FK/RLS
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    # Client-side default: inserts must not need RETURNING, because most roles cannot SELECT audit rows.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
