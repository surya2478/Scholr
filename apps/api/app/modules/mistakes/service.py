"""Mistake bank: patterns projected from ``mistake_diagnosed`` and clean ``attempt_evaluated`` events (§14).

Status: open -> improving (2 consecutive clean final attempts on the objective) -> resolved (clean on >= 2 distinct
days including a retention item); a recurrence reopens the pattern. Rows are rebuildable from events; pattern
descriptions come from the evaluation that diagnosed them and are passed in by the caller.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.curriculum import service as curriculum
from app.modules.events import service as events
from app.modules.mistakes.models import MISTAKE_TYPES, MistakeOccurrence, MistakePattern
from app.modules.mistakes.schemas import MistakeOut

__all__ = ["MISTAKE_TYPES", "derive_patterns", "list_mistakes", "open_high_severity_objectives", "project", "recompute"]

UNRESOLVED = ("open", "improving")
PROJECTED_TYPES = ("attempt_evaluated", "mistake_diagnosed")
IMPROVING_STREAK = 2
RESOLVED_DISTINCT_DAYS = 2

PatternKey = tuple[UUID, str, str]  # objective_id, mistake_type, fingerprint


@dataclass
class PatternState:
    objective_id: UUID
    subject_id: UUID
    mistake_type: str
    fingerprint: str
    severity: str
    first_seen: datetime
    last_seen: datetime
    last_evaluation_id: UUID
    occurrences: list[tuple[UUID, UUID, datetime]] = field(default_factory=list)  # attempt, evaluation, time
    clean_streak: int = 0
    clean_days: set[date] = field(default_factory=set)
    retention_clean: bool = False
    status: str = "open"


def derive_patterns(history: Sequence[events.EventView]) -> dict[PatternKey, PatternState]:
    """Pure: ordered events -> pattern states."""
    with_mistakes = {str(ev.payload.get("evaluation_id")) for ev in history if ev.type == "mistake_diagnosed"}
    states: dict[PatternKey, PatternState] = {}
    for ev in history:
        if ev.type == "mistake_diagnosed" and ev.subject_id is not None:
            p = events.MistakeDiagnosed.model_validate(ev.payload)
            for objective_id in ev.objective_ids:
                key = (objective_id, p.mistake_type, p.fingerprint)
                state = states.get(key)
                if state is None:
                    state = states[key] = PatternState(
                        objective_id=objective_id,
                        subject_id=ev.subject_id,
                        mistake_type=p.mistake_type,
                        fingerprint=p.fingerprint,
                        severity=p.severity,
                        first_seen=ev.occurred_at,
                        last_seen=ev.occurred_at,
                        last_evaluation_id=p.evaluation_id,
                    )
                state.occurrences.append((p.attempt_id, p.evaluation_id, ev.occurred_at))
                state.last_seen, state.severity, state.last_evaluation_id = ev.occurred_at, p.severity, p.evaluation_id
                state.clean_streak, state.clean_days, state.retention_clean = 0, set(), False
                state.status = "open"
        elif ev.type == "attempt_evaluated":
            p = events.AttemptEvaluated.model_validate(ev.payload)
            if p.status != "final" or str(p.evaluation_id) in with_mistakes:
                continue
            for state in states.values():
                if state.objective_id not in ev.objective_ids or state.status == "resolved":
                    continue
                state.clean_streak += 1
                state.clean_days.add(ev.occurred_at.date())
                state.retention_clean = state.retention_clean or p.retention_check
                if len(state.clean_days) >= RESOLVED_DISTINCT_DAYS and state.retention_clean:
                    state.status = "resolved"
                elif state.clean_streak >= IMPROVING_STREAK:
                    state.status = "improving"
    return states


def recompute(
    s: Session,
    *,
    tenant_id: UUID,
    student_id: UUID,
    objective_ids: Sequence[UUID],
    descriptions: Mapping[tuple[UUID, str], str] | None = None,
) -> None:
    wanted = list(dict.fromkeys(objective_ids))
    if not wanted:
        return
    descriptions = descriptions or {}
    history = events.list_events(s, student_id=student_id, types=PROJECTED_TYPES, objective_ids=wanted)
    states = {key: st for key, st in derive_patterns(history).items() if key[0] in wanted}
    existing = {
        (row.objective_id, row.mistake_type, row.fingerprint): row
        for row in s.scalars(
            select(MistakePattern).where(
                MistakePattern.student_id == student_id, MistakePattern.objective_id.in_(wanted)
            )
        )
    }
    objectives = curriculum.objective_summaries(s, wanted)
    for key, row in existing.items():
        if key not in states:
            s.delete(row)

    for key, st in states.items():
        row = existing.get(key)
        description = descriptions.get((st.last_evaluation_id, st.fingerprint)) or (
            row.description if row is not None else st.fingerprint.replace(":", " - ").replace("_", " ")
        )
        values = {
            "subject_id": st.subject_id,
            "topic_id": objectives[st.objective_id].topic_id if st.objective_id in objectives else None,
            "description": description,
            "occurrences": len(st.occurrences),
            "severity": st.severity,
            "first_seen": st.first_seen,
            "last_seen": st.last_seen,
            "clean_streak": st.clean_streak,
            "status": st.status,
        }
        if row is None:
            row = MistakePattern(
                tenant_id=tenant_id,
                student_id=student_id,
                objective_id=st.objective_id,
                mistake_type=st.mistake_type,
                fingerprint=st.fingerprint,
                **values,
            )
            s.add(row)
            s.flush()
        else:
            for name, value in values.items():
                setattr(row, name, value)
            s.execute(delete(MistakeOccurrence).where(MistakeOccurrence.pattern_id == row.id))
        s.add_all(
            MistakeOccurrence(
                tenant_id=tenant_id,
                student_id=student_id,
                pattern_id=row.id,
                attempt_id=attempt_id,
                evaluation_id=evaluation_id,
                occurred_at=occurred_at,
            )
            for attempt_id, evaluation_id, occurred_at in st.occurrences
        )
    s.flush()


def project(
    s: Session,
    new_events: Sequence[events.EventView],
    *,
    tenant_id: UUID,
    descriptions: Mapping[tuple[UUID, str], str] | None = None,
) -> None:
    """Synchronous projection hook (AC-M2): call right after appending events, in the same transaction."""
    touched: dict[UUID, list[UUID]] = defaultdict(list)
    for ev in new_events:
        if ev.type in PROJECTED_TYPES:
            touched[ev.student_id].extend(ev.objective_ids)
    for student_id, objective_ids in touched.items():
        recompute(s, tenant_id=tenant_id, student_id=student_id, objective_ids=objective_ids, descriptions=descriptions)


def open_high_severity_objectives(s: Session, student_id: UUID, objective_ids: Sequence[UUID]) -> set[UUID]:
    if not objective_ids:
        return set()
    return {
        oid
        for oid in s.scalars(
            select(MistakePattern.objective_id).where(
                MistakePattern.student_id == student_id,
                MistakePattern.objective_id.in_(list(objective_ids)),
                MistakePattern.severity == "high",
                MistakePattern.status.in_(UNRESOLVED),
            )
        )
        if oid is not None
    }


def list_mistakes(
    s: Session, *, student_id: UUID, subject_id: UUID | None = None, status: str | None = None
) -> list[MistakeOut]:
    query = select(MistakePattern).where(MistakePattern.student_id == student_id)
    if subject_id is not None:
        query = query.where(MistakePattern.subject_id == subject_id)
    if status is not None:
        query = query.where(MistakePattern.status == status)
    rows = s.scalars(query.order_by(MistakePattern.last_seen.desc())).all()
    objectives = curriculum.objective_summaries(s, [r.objective_id for r in rows if r.objective_id])
    return [
        MistakeOut(
            id=r.id,
            subject_id=r.subject_id,
            objective_id=r.objective_id,
            objective_code=objectives[r.objective_id].code if r.objective_id in objectives else None,
            mistake_type=r.mistake_type,
            fingerprint=r.fingerprint,
            description=r.description,
            severity=r.severity,
            occurrences=r.occurrences,
            status=r.status,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
            resolution=r.resolution,
        )
        for r in rows
    ]
