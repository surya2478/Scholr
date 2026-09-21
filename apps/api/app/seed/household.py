"""Idempotent seed for one household: tenant, student, guardians, enrollments, commitments.

Usage: uv run python -m app.seed.household ../../content/private/seed/household.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import Subject
from app.modules.enrollment.models import Availability, Commitment, Enrollment
from app.modules.identity.models import GUARDIAN_SCOPES, AppUser, Guardian, GuardianStudentLink, Student, Tenant


class PersonIn(BaseModel):
    display_name: str
    auth_subject: str
    email: str | None = None


class StudentIn(PersonIn):
    year_group: str
    timezone: str = "Asia/Dubai"


class GuardianIn(PersonIn):
    scopes: Literal["all"] | list[str] = "all"


class EnrollmentIn(BaseModel):
    subject: str
    tier: str | None = None
    exam_session: str | None = None


class CommitmentIn(BaseModel):
    kind: Literal["iit_class", "extracurricular", "school", "other"]
    title: str
    rrule: str
    start_time: str | None = None
    duration_min: int
    notes: str | None = None


class HouseholdIn(BaseModel):
    tenant: dict[str, str]
    student: StudentIn
    guardians: list[GuardianIn] = Field(default_factory=list)
    enrollments: list[EnrollmentIn] = Field(default_factory=list)
    commitments: list[CommitmentIn] = Field(default_factory=list)
    availability_minutes: list[int] | None = None


def _upsert_user(s: Session, tenant_id: UUID, person: PersonIn, role: str) -> AppUser:
    user = s.scalar(select(AppUser).where(AppUser.auth_subject == person.auth_subject))
    if user is None:
        user = AppUser(
            tenant_id=tenant_id,
            auth_subject=person.auth_subject,
            role=role,
            display_name=person.display_name,
            email=person.email,
        )
        s.add(user)
    else:
        user.display_name, user.email = person.display_name, person.email
    s.flush()
    return user


def seed_household(s: Session, data: HouseholdIn) -> dict[str, Any]:
    tenant = s.scalar(select(Tenant).where(Tenant.name == data.tenant["name"]))
    if tenant is None:
        tenant = Tenant(name=data.tenant["name"])
        s.add(tenant)
        s.flush()

    student_user = _upsert_user(s, tenant.id, data.student, "student")
    student = s.scalar(select(Student).where(Student.user_id == student_user.id))
    if student is None:
        student = Student(
            tenant_id=tenant.id,
            user_id=student_user.id,
            display_name=data.student.display_name,
            year_group=data.student.year_group,
            timezone=data.student.timezone,
        )
        s.add(student)
    else:
        student.display_name, student.year_group = data.student.display_name, data.student.year_group
        student.timezone = data.student.timezone
    s.flush()

    for g in data.guardians:
        g_user = _upsert_user(s, tenant.id, g, "guardian")
        guardian = s.scalar(select(Guardian).where(Guardian.user_id == g_user.id))
        if guardian is None:
            guardian = Guardian(tenant_id=tenant.id, user_id=g_user.id)
            s.add(guardian)
            s.flush()
        scopes = list(GUARDIAN_SCOPES) if g.scopes == "all" else [x for x in g.scopes if x in GUARDIAN_SCOPES]
        link = s.scalar(
            select(GuardianStudentLink).where(
                GuardianStudentLink.guardian_id == guardian.id, GuardianStudentLink.student_id == student.id
            )
        )
        if link is None:
            s.add(
                GuardianStudentLink(tenant_id=tenant.id, guardian_id=guardian.id, student_id=student.id, scopes=scopes)
            )
        else:
            link.scopes, link.revoked_at = scopes, None

    for e in data.enrollments:
        subject = s.scalar(select(Subject).where(Subject.code == e.subject))
        if subject is None:
            raise ValueError(f"unknown subject '{e.subject}' — run the curriculum seed first")
        row = s.scalar(
            select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.subject_id == subject.id)
        )
        if row is None:
            s.add(
                Enrollment(
                    tenant_id=tenant.id,
                    student_id=student.id,
                    subject_id=subject.id,
                    tier=e.tier,
                    exam_session=e.exam_session,
                )
            )
        else:
            row.tier, row.exam_session = e.tier, e.exam_session

    # The seed's commitment list is the full set: rows not listed (for example an old placeholder) are removed.
    wanted_titles = {c.title for c in data.commitments}
    for old in s.scalars(select(Commitment).where(Commitment.student_id == student.id)).all():
        if old.title not in wanted_titles:
            s.delete(old)
    for c in data.commitments:
        exists = s.scalar(select(Commitment).where(Commitment.student_id == student.id, Commitment.title == c.title))
        if exists is None:
            s.add(Commitment(tenant_id=tenant.id, student_id=student.id, **c.model_dump()))
        else:
            exists.kind, exists.rrule = c.kind, c.rrule
            exists.start_time, exists.duration_min, exists.notes = c.start_time, c.duration_min, c.notes

    if data.availability_minutes is not None:
        if len(data.availability_minutes) != 7:
            raise ValueError("availability_minutes needs 7 values (Monday..Sunday)")
        for weekday, minutes in enumerate(data.availability_minutes):
            row = s.scalar(
                select(Availability).where(Availability.student_id == student.id, Availability.weekday == weekday)
            )
            if row is None:
                s.add(Availability(tenant_id=tenant.id, student_id=student.id, weekday=weekday, minutes=minutes))
            else:
                row.minutes = minutes

    s.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_role="system",
            action="seed.household",
            entity_type="student",
            entity_id=student.id,
            student_id=student.id,
        )
    )
    s.flush()
    return {"tenant_id": tenant.id, "student_id": student.id, "student_user_id": student_user.id}


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: python -m app.seed.household <household.yaml>")
    data = HouseholdIn.model_validate(yaml.safe_load(Path(argv[1]).read_text(encoding="utf-8")))
    with session_scope(user_id=None, role="system") as s:
        result = seed_household(s, data)
    print({k: str(v) for k, v in result.items()})


if __name__ == "__main__":
    main(sys.argv)
