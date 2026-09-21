from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.studies import service
from app.modules.studies.schemas import AssignmentOut, PairCreate, StudyResultsOut

router = APIRouter(tags=["studies"])


@router.post("/studies/assignments", response_model=list[AssignmentOut], status_code=201)
def post_pair(
    body: PairCreate, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> list[AssignmentOut]:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.create_pair(s, principal, body, student_id=sid, now=datetime.now(UTC))


@router.get("/studies/assignments", response_model=list[AssignmentOut])
def get_assignments(
    principal: PrincipalDep, s: DbDep, student_id: UUID | None = None, subject_id: UUID | None = None
) -> list[AssignmentOut]:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.list_assignments(s, principal, student_id=sid, subject_id=subject_id)


@router.get("/studies/{subject_id}/results", response_model=StudyResultsOut)
def get_results(subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> StudyResultsOut:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.study_results(s, principal, student_id=sid, subject_id=subject_id, now=datetime.now(UTC))


@router.post("/studies/{subject_id}/crossover", response_model=list[AssignmentOut])
def post_crossover(
    subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> list[AssignmentOut]:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.crossover(s, principal, student_id=sid, subject_id=subject_id, now=datetime.now(UTC))
