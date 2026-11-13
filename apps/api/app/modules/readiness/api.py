from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.identity import service as identity
from app.modules.readiness import service, timed
from app.modules.readiness.schemas import PastPaperOut, ReadinessOut, SittingIn, SittingOut, TimedQuestionOut
from app.tools.dates import local_date

router = APIRouter(tags=["readiness"])


@router.get("/subjects/{subject_id}/readiness", response_model=ReadinessOut)
def get_readiness(subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    today = local_date(datetime.now(UTC), identity.student_timezone(s, sid))
    return service.readiness(s, principal, student_id=sid, subject_id=subject_id, today=today)


@router.get("/subjects/{subject_id}/past-papers", response_model=list[PastPaperOut])
def get_past_papers(subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.past_papers(s, principal, student_id=sid, subject_id=subject_id)


@router.post("/subjects/{subject_id}/sittings", response_model=SittingOut, status_code=201)
def post_sitting(subject_id: UUID, body: SittingIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    sid = resolve_student_id(principal, student_id, scope="assessments")
    return service.start_sitting(s, principal, student_id=sid, subject_id=subject_id, body=body, now=datetime.now(UTC))


@router.get("/sittings/{assessment_id}", response_model=SittingOut)
def get_sitting(assessment_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    sid = resolve_student_id(principal, student_id, scope="assessments")
    return service.sitting(s, principal, student_id=sid, assessment_id=assessment_id, now=datetime.now(UTC))


@router.get("/timed-questions", response_model=list[TimedQuestionOut])
def get_timed_questions(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    """This week's timed long answer in each subject that has one (improvement 4)."""
    sid = resolve_student_id(principal, student_id, scope=timed.SCOPE)
    return timed.this_week(s, principal, student_id=sid, now=datetime.now(UTC))


@router.post("/subjects/{subject_id}/timed-question", response_model=TimedQuestionOut, status_code=201)
def post_timed_question(subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    sid = resolve_student_id(principal, student_id, scope=timed.SCOPE)
    return timed.start(s, principal, student_id=sid, subject_id=subject_id, now=datetime.now(UTC))
