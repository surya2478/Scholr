"""Identity: resolve the caller from a verified token subject, and describe them (GET /me)."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import Principal
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.identity.models import AppUser, Guardian, GuardianStudentLink, Student, Tenant
from app.modules.identity.schemas import (
    EnrollmentOut,
    GuardianVisibilityOut,
    LinkedStudentOut,
    MeOut,
    StudentOut,
    UserOut,
)
from app.modules.subjects import service as subjects


def resolve_principal(s: Session, auth_subject: str, *, mfa: bool) -> Principal | None:
    user = s.scalar(select(AppUser).where(AppUser.auth_subject == auth_subject))
    if user is None or user.status != "active":
        return None
    base = {
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "display_name": user.display_name,
        "mfa": mfa,
    }
    if user.role == "student":
        student_id = s.scalar(select(Student.id).where(Student.user_id == user.id))
        return Principal(**base, student_id=student_id) if student_id else None
    if user.role == "guardian":
        guardian_id = s.scalar(select(Guardian.id).where(Guardian.user_id == user.id))
        if guardian_id is None:
            return None
        links = s.execute(
            select(GuardianStudentLink.student_id, GuardianStudentLink.scopes).where(
                GuardianStudentLink.guardian_id == guardian_id, GuardianStudentLink.revoked_at.is_(None)
            )
        ).all()
        return Principal(
            **base, guardian_id=guardian_id, guardian_scopes={sid: frozenset(scopes) for sid, scopes in links}
        )
    return Principal(**base)


def student_display_name(s: Session, student_id: UUID) -> str:
    return s.scalar(select(Student.display_name).where(Student.id == student_id)) or ""


def student_timezone(s: Session, student_id: UUID) -> str:
    return s.scalar(select(Student.timezone).where(Student.id == student_id)) or "UTC"


def _answer_input(subject_code: str) -> str:
    try:
        return subjects.taught_config_for(subject_code).answer_input
    except subjects.SubjectConfigError:
        return "text"


def _stage(subject_code: str) -> str:
    try:
        return subjects.config_for(subject_code).stage
    except subjects.SubjectConfigError:
        return "taught"


def _enrollments_by_student(s: Session, student_ids: list[UUID]) -> dict[UUID, list[EnrollmentOut]]:
    views = enrollment.list_enrollments(s, student_ids)
    subjects = curriculum.subject_summaries(s, [v.subject_id for v in views])
    grouped: dict[UUID, list[EnrollmentOut]] = defaultdict(list)
    for v in views:
        subject = subjects[v.subject_id]
        grouped[v.student_id].append(
            EnrollmentOut(
                subject_id=v.subject_id,
                subject_code=subject.code,
                subject_name=subject.name,
                tier=v.tier,
                exam_session=v.exam_session,
                answer_input=_answer_input(subject.code),
                stage=_stage(subject.code),
            )
        )
    for items in grouped.values():
        items.sort(key=lambda e: e.subject_name)
    return grouped


def me(s: Session, principal: Principal) -> MeOut:
    out = MeOut(user=UserOut(id=principal.user_id, display_name=principal.display_name, role=principal.role))
    enrollments = _enrollments_by_student(s, principal.visible_student_ids)

    if principal.role == "student" and principal.student_id:
        student = s.get(Student, principal.student_id)
        assert student is not None
        out.student = StudentOut(
            id=student.id,
            display_name=student.display_name,
            year_group=student.year_group,
            timezone=student.timezone,
            enrollments=enrollments.get(student.id, []),
        )
        rows = s.execute(
            select(AppUser.display_name, GuardianStudentLink.scopes)
            .join(Guardian, Guardian.user_id == AppUser.id)
            .join(GuardianStudentLink, GuardianStudentLink.guardian_id == Guardian.id)
            .where(GuardianStudentLink.student_id == student.id, GuardianStudentLink.revoked_at.is_(None))
            .order_by(AppUser.display_name)
        ).all()
        out.guardian_visibility = [GuardianVisibilityOut(guardian_name=name, scopes=sorted(sc)) for name, sc in rows]

    if principal.role == "guardian" and principal.guardian_scopes:
        students = s.scalars(
            select(Student).where(Student.id.in_(list(principal.guardian_scopes))).order_by(Student.display_name)
        ).all()
        out.linked_students = [
            LinkedStudentOut(
                id=st.id,
                display_name=st.display_name,
                year_group=st.year_group,
                timezone=st.timezone,
                enrollments=enrollments.get(st.id, []),
                scopes=sorted(principal.guardian_scopes[st.id]),
            )
            for st in students
        ]
    return out


def default_tenant_id(s: Session) -> UUID | None:
    """The household's tenant. One tenant today; a registration joins it (docs/STUDENT-APP.md D7)."""
    return s.scalar(select(Tenant.id).order_by(Tenant.created_at).limit(1))


def dev_account_subject(s: Session, role: str) -> str | None:
    """The seeded account to sign in as while sign-in is not built (AUTH_MODE=dev only)."""
    return s.scalar(
        select(AppUser.auth_subject)
        .where(AppUser.role == role, AppUser.status == "active")
        .order_by(AppUser.created_at)
        .limit(1)
    )
