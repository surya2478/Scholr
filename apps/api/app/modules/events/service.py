"""Append-only learning events: the single write path for learning evidence, plus reads for projections.

Features call ``append`` and then hand the returned events to the projections that consume them
(mastery is updated synchronously in the same transaction).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.events.models import LearningEvent
from app.modules.events.schemas import (
    PAYLOAD_SCHEMAS,
    REQUIRES_OBJECTIVES,
    SCHEMA_VERSION,
    AttemptEvaluated,
    EvaluationOverridden,
    MistakeDiagnosed,
)

__all__ = [
    "AttemptEvaluated",
    "EvaluationOverridden",
    "EventValidationError",
    "EventView",
    "MistakeDiagnosed",
    "append",
    "list_events",
]

FUTURE_TOLERANCE = timedelta(minutes=5)


class EventValidationError(ValueError):
    pass


@dataclass(frozen=True)
class EventView:
    id: UUID
    student_id: UUID
    type: str
    occurred_at: datetime
    subject_id: UUID | None
    objective_ids: tuple[UUID, ...]
    payload: dict[str, Any]
    ref_type: str | None = None
    ref_id: UUID | None = None


def validate_event(
    event_type: str,
    payload: BaseModel | dict[str, Any],
    *,
    occurred_at: datetime,
    objective_ids: Sequence[UUID],
    now: datetime,
) -> dict[str, Any]:
    """Return the normalised payload, or raise EventValidationError. Error text never echoes values."""
    schema = PAYLOAD_SCHEMAS.get(event_type)
    if schema is None:
        raise EventValidationError(f"unknown event type: {event_type}")
    if occurred_at.tzinfo is None:
        raise EventValidationError("occurred_at must be timezone-aware")
    if occurred_at > now + FUTURE_TOLERANCE:
        raise EventValidationError("occurred_at is in the future")
    if event_type in REQUIRES_OBJECTIVES and not objective_ids:
        raise EventValidationError(f"{event_type} needs at least one objective id")
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    try:
        return schema.model_validate(data).model_dump(mode="json")
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) or "(root)" for err in exc.errors()})
        raise EventValidationError(f"{event_type}: invalid payload fields {fields}") from None


def _view(row: LearningEvent) -> EventView:
    return EventView(
        id=row.id,
        student_id=row.student_id,
        type=row.type,
        occurred_at=row.occurred_at,
        subject_id=row.subject_id,
        objective_ids=tuple(row.objective_ids or ()),
        payload=dict(row.payload or {}),
        ref_type=row.ref_type,
        ref_id=row.ref_id,
    )


def append(
    s: Session,
    *,
    tenant_id: UUID,
    student_id: UUID,
    event_type: str,
    occurred_at: datetime,
    payload: BaseModel | dict[str, Any],
    subject_id: UUID | None = None,
    objective_ids: Sequence[UUID] = (),
    ref_type: str | None = None,
    ref_id: UUID | None = None,
) -> EventView:
    clean = validate_event(
        event_type, payload, occurred_at=occurred_at, objective_ids=objective_ids, now=datetime.now(UTC)
    )
    row = LearningEvent(
        tenant_id=tenant_id,
        student_id=student_id,
        occurred_at=occurred_at,
        type=event_type,
        subject_id=subject_id,
        objective_ids=list(dict.fromkeys(objective_ids)),
        payload=clean,
        schema_version=SCHEMA_VERSION,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    s.add(row)
    s.flush()
    return _view(row)


def events_by_ids(s: Session, event_ids: Sequence[UUID]) -> list[EventView]:
    if not event_ids:
        return []
    rows = s.scalars(select(LearningEvent).where(LearningEvent.id.in_(list(event_ids))))
    return [_view(row) for row in rows]


def list_events(
    s: Session,
    *,
    student_id: UUID,
    types: Sequence[str] | None = None,
    objective_ids: Sequence[UUID] | None = None,
    since: datetime | None = None,
) -> list[EventView]:
    """Events in occurrence order. ``objective_ids`` keeps events tagged with any of them."""
    query = select(LearningEvent).where(LearningEvent.student_id == student_id)
    if since is not None:
        query = query.where(LearningEvent.occurred_at >= since)
    if types:
        query = query.where(LearningEvent.type.in_(list(types)))
    if objective_ids is not None:
        if not objective_ids:
            return []
        query = query.where(LearningEvent.objective_ids.overlap(list(objective_ids)))
    query = query.order_by(LearningEvent.occurred_at, LearningEvent.recorded_at, LearningEvent.id)
    return [_view(row) for row in s.scalars(query)]
