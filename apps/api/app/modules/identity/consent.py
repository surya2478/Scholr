"""Consent records (ARCHITECTURE §5.1): guardian consent and student assent, versioned by policy, withdrawable,
audited."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.audit import service as audit
from app.modules.identity.models import ConsentRecord

POLICY_VERSION = "privacy_v1"
KIND_FOR_ROLE = {"guardian": "guardian_consent", "student": "student_assent"}


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str = POLICY_VERSION


class ConsentOut(BaseModel):
    id: UUID
    student_id: UUID
    user_id: UUID
    kind: str
    policy_version: str
    granted_at: datetime
    withdrawn_at: datetime | None


def _out(row: ConsentRecord) -> ConsentOut:
    return ConsentOut(
        id=row.id,
        student_id=row.student_id,
        user_id=row.user_id,
        kind=row.kind,
        policy_version=row.policy_version,
        granted_at=row.granted_at,
        withdrawn_at=row.withdrawn_at,
    )


def list_consents(s: Session, principal: Principal, *, student_id: UUID) -> list[ConsentOut]:
    require_student_access(principal, student_id)
    rows = s.scalars(
        select(ConsentRecord).where(ConsentRecord.student_id == student_id).order_by(ConsentRecord.granted_at.desc())
    )
    return [_out(r) for r in rows]


def record_consent(s: Session, principal: Principal, body: ConsentIn, *, student_id: UUID, now: datetime) -> ConsentOut:
    """A guardian records consent, or the student records assent, for the current policy version (idempotent)."""
    require_student_access(principal, student_id)
    kind = KIND_FOR_ROLE.get(principal.role)
    if kind is None:
        raise ApiError(403, "forbidden", "only the student or a linked guardian can record consent")
    if body.policy_version != POLICY_VERSION:
        raise ApiError(422, "unknown_policy_version", f"the current policy is {POLICY_VERSION}")
    existing = s.scalar(
        select(ConsentRecord).where(
            ConsentRecord.student_id == student_id,
            ConsentRecord.user_id == principal.user_id,
            ConsentRecord.kind == kind,
            ConsentRecord.policy_version == body.policy_version,
            ConsentRecord.withdrawn_at.is_(None),
        )
    )
    if existing is not None:
        return _out(existing)
    row = ConsentRecord(
        tenant_id=principal.tenant_id,
        student_id=student_id,
        user_id=principal.user_id,
        kind=kind,
        policy_version=body.policy_version,
        granted_at=now,
    )
    s.add(row)
    s.flush()
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="consent.recorded",
        entity_type="consent_record",
        entity_id=row.id,
        student_id=student_id,
        meta={"kind": kind, "policy_version": body.policy_version},
    )
    return _out(row)


def withdraw_consent(s: Session, principal: Principal, consent_id: UUID, *, now: datetime) -> ConsentOut:
    row = s.get(ConsentRecord, consent_id)
    if row is None:
        raise not_found("consent")
    if row.user_id != principal.user_id:
        raise ApiError(403, "forbidden", "only the person who gave consent can withdraw it")
    if row.withdrawn_at is None:
        row.withdrawn_at = now
        s.flush()
        audit.record(
            s,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            action="consent.withdrawn",
            entity_type="consent_record",
            entity_id=row.id,
            student_id=row.student_id,
            meta={"kind": row.kind, "policy_version": row.policy_version},
        )
    return _out(row)
