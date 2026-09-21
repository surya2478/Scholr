"""Audit log writes. Metadata must never contain conversation text or answers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


@dataclass(frozen=True)
class AuditEntry:
    id: UUID
    created_at: datetime
    actor_user_id: UUID | None
    actor_role: str
    action: str
    entity_type: str
    entity_id: UUID | None
    student_id: UUID | None
    meta: dict[str, Any]


def list_entries(
    s: Session, *, student_id: UUID | None = None, action_prefix: str | None = None, limit: int = 100
) -> list[AuditEntry]:
    """Newest first. Row-level security lets only admin (and system) sessions read audit rows."""
    query = select(AuditLog)
    if student_id is not None:
        query = query.where(AuditLog.student_id == student_id)
    if action_prefix:
        query = query.where(AuditLog.action.startswith(action_prefix))
    rows = s.scalars(query.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)))
    return [
        AuditEntry(
            r.id,
            r.created_at,
            r.actor_user_id,
            r.actor_role,
            r.action,
            r.entity_type,
            r.entity_id,
            r.student_id,
            dict(r.meta or {}),
        )
        for r in rows
    ]


def record(
    s: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    student_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    s.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            student_id=student_id,
            meta=meta or {},
        )
    )
    s.flush()
