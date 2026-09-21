"""Enrollment and schedule data: enrollments, availability, commitments, teaching plan, upcoming assessments and
school results. Row-level security limits every read and write to students the caller may access."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.modules.enrollment.models import (
    Availability,
    Commitment,
    Enrollment,
    SchoolResult,
    TeachingPlanEntry,
    UpcomingAssessment,
)
from app.modules.enrollment.schemas import (
    CommitmentIn,
    CommitmentOut,
    SchoolResultIn,
    SchoolResultOut,
    TeachingEntryIn,
    TeachingEntryOut,
    UpcomingIn,
    UpcomingOut,
)
from app.modules.events import service as events


@dataclass(frozen=True)
class EnrollmentView:
    student_id: UUID
    subject_id: UUID
    tier: str | None
    exam_session: str | None


def list_enrollments(s: Session, student_ids: Sequence[UUID]) -> list[EnrollmentView]:
    if not student_ids:
        return []
    rows = s.execute(
        select(Enrollment.student_id, Enrollment.subject_id, Enrollment.tier, Enrollment.exam_session).where(
            Enrollment.student_id.in_(list(student_ids)), Enrollment.status == "active"
        )
    ).all()
    return [EnrollmentView(*row) for row in rows]


# --- availability ---------------------------------------------------------------------------------------------


def enroll_in_subjects(s: Session, *, tenant_id: UUID, student_id: UUID, subject_ids: Sequence[UUID]) -> list[UUID]:
    """Enroll a student in subjects she is not enrolled in yet; returns the ones added (docs/STUDENT-APP.md D7)."""
    existing = set(s.scalars(select(Enrollment.subject_id).where(Enrollment.student_id == student_id)))
    added: list[UUID] = []
    for subject_id in subject_ids:
        if subject_id in existing:
            continue
        s.add(Enrollment(tenant_id=tenant_id, student_id=student_id, subject_id=subject_id, status="active"))
        existing.add(subject_id)
        added.append(subject_id)
    s.flush()
    return added


def availability(s: Session, *, student_id: UUID) -> dict[int, int]:
    return dict(
        s.execute(select(Availability.weekday, Availability.minutes).where(Availability.student_id == student_id)).all()
    )


def set_availability(s: Session, *, tenant_id: UUID, student_id: UUID, minutes: Sequence[int]) -> dict[int, int]:
    existing = {a.weekday: a for a in s.scalars(select(Availability).where(Availability.student_id == student_id))}
    for weekday, value in enumerate(minutes):
        if weekday in existing:
            existing[weekday].minutes = value
        else:
            s.add(Availability(tenant_id=tenant_id, student_id=student_id, weekday=weekday, minutes=value))
    s.flush()
    return availability(s, student_id=student_id)


# --- commitments ----------------------------------------------------------------------------------------------


def _commitment_out(row: Commitment) -> CommitmentOut:
    return CommitmentOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        rrule=row.rrule,
        start_time=row.start_time,
        duration_min=row.duration_min,
        notes=row.notes,
    )


def list_commitments(s: Session, *, student_id: UUID) -> list[CommitmentOut]:
    rows = s.scalars(select(Commitment).where(Commitment.student_id == student_id).order_by(Commitment.title))
    return [_commitment_out(r) for r in rows]


def add_commitment(s: Session, *, tenant_id: UUID, student_id: UUID, body: CommitmentIn) -> CommitmentOut:
    row = Commitment(tenant_id=tenant_id, student_id=student_id, **body.model_dump())
    s.add(row)
    s.flush()
    return _commitment_out(row)


def delete_commitment(s: Session, *, commitment_id: UUID) -> UUID:
    row = s.get(Commitment, commitment_id)
    if row is None:
        raise not_found("commitment")
    student_id = row.student_id
    s.delete(row)
    s.flush()
    return student_id


def commitment_student(s: Session, commitment_id: UUID) -> UUID:
    row = s.get(Commitment, commitment_id)
    if row is None:
        raise not_found("commitment")
    return row.student_id


# --- teaching plan --------------------------------------------------------------------------------------------


def _teaching_out(row: TeachingPlanEntry) -> TeachingEntryOut:
    return TeachingEntryOut(
        id=row.id,
        subject_id=row.subject_id,
        term=row.term,
        label=row.label,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        topic_ids=list(row.topic_ids or []),
        source=row.source,
    )


def list_teaching_entries(s: Session, *, student_id: UUID) -> list[TeachingEntryOut]:
    rows = s.scalars(
        select(TeachingPlanEntry)
        .where(TeachingPlanEntry.student_id == student_id)
        .order_by(TeachingPlanEntry.starts_on)
    )
    return [_teaching_out(r) for r in rows]


def teaching_entries_on(s: Session, *, student_id: UUID, day: date) -> list[TeachingEntryOut]:
    rows = s.scalars(
        select(TeachingPlanEntry).where(
            TeachingPlanEntry.student_id == student_id,
            or_(TeachingPlanEntry.starts_on.is_(None), TeachingPlanEntry.starts_on <= day),
            or_(TeachingPlanEntry.ends_on.is_(None), TeachingPlanEntry.ends_on >= day),
        )
    )
    return [_teaching_out(r) for r in rows]


def add_teaching_entry(s: Session, *, tenant_id: UUID, student_id: UUID, body: TeachingEntryIn) -> TeachingEntryOut:
    row = TeachingPlanEntry(tenant_id=tenant_id, student_id=student_id, **body.model_dump())
    s.add(row)
    s.flush()
    return _teaching_out(row)


def teaching_entry_student(s: Session, entry_id: UUID) -> UUID:
    row = s.get(TeachingPlanEntry, entry_id)
    if row is None:
        raise not_found("teaching plan entry")
    return row.student_id


def delete_teaching_entry(s: Session, *, entry_id: UUID) -> None:
    s.execute(delete(TeachingPlanEntry).where(TeachingPlanEntry.id == entry_id))


# --- upcoming assessments -------------------------------------------------------------------------------------


def _upcoming_out(row: UpcomingAssessment) -> UpcomingOut:
    return UpcomingOut(
        id=row.id,
        subject_id=row.subject_id,
        title=row.title,
        due_at=row.due_at,
        objective_ids=list(row.objective_ids or []),
        notes=row.notes,
    )


def list_upcoming_assessments(
    s: Session, *, student_id: UUID, start: datetime | None = None, end: datetime | None = None
) -> list[UpcomingOut]:
    conditions = [UpcomingAssessment.student_id == student_id]
    if start is not None:
        conditions.append(UpcomingAssessment.due_at >= start)
    if end is not None:
        conditions.append(UpcomingAssessment.due_at <= end)
    rows = s.scalars(select(UpcomingAssessment).where(and_(*conditions)).order_by(UpcomingAssessment.due_at))
    return [_upcoming_out(r) for r in rows]


def add_upcoming_assessment(s: Session, *, tenant_id: UUID, student_id: UUID, body: UpcomingIn) -> UpcomingOut:
    row = UpcomingAssessment(tenant_id=tenant_id, student_id=student_id, **body.model_dump())
    s.add(row)
    s.flush()
    return _upcoming_out(row)


def upcoming_student(s: Session, upcoming_id: UUID) -> UUID:
    row = s.get(UpcomingAssessment, upcoming_id)
    if row is None:
        raise not_found("upcoming assessment")
    return row.student_id


def delete_upcoming_assessment(s: Session, *, upcoming_id: UUID) -> None:
    s.execute(delete(UpcomingAssessment).where(UpcomingAssessment.id == upcoming_id))


# --- school results -------------------------------------------------------------------------------------------


def record_school_result(
    s: Session, *, tenant_id: UUID, student_id: UUID, body: SchoolResultIn, now: datetime
) -> SchoolResultOut:
    row = SchoolResult(tenant_id=tenant_id, student_id=student_id, **body.model_dump())
    s.add(row)
    s.flush()
    events.append(
        s,
        tenant_id=tenant_id,
        student_id=student_id,
        event_type="school_result_recorded",
        occurred_at=now,
        payload={"school_result_id": row.id, "score": float(body.score), "max_score": float(body.max_score)},
        subject_id=body.subject_id,
        objective_ids=list(body.objective_ids),
        ref_type="school_result",
        ref_id=row.id,
    )
    return SchoolResultOut(id=row.id, **body.model_dump())
