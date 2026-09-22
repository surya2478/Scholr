from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request

from app.core.deps import DbDep, PrincipalDep, SessionsDep, llm_gateway
from app.core.rbac import resolve_student_id
from app.core.telemetry import request_id_of
from app.llm.gateway import CallContext
from app.modules.assessment.schemas import ExaminerInsightsOut
from app.modules.evaluation import service
from app.modules.evaluation.schemas import (
    AutopsyEntryOut,
    AutopsyIn,
    EvaluationOut,
    OverrideIn,
    ReviewItemOut,
)

router = APIRouter(tags=["evaluation"])


@router.post("/attempts/{attempt_id}/evaluate", response_model=EvaluationOut)
def evaluate_attempt(
    attempt_id: UUID, request: Request, principal: PrincipalDep, sessions: SessionsDep
) -> EvaluationOut:
    with sessions() as s:
        prepared = service.prepare(s, principal, attempt_id)
    if isinstance(prepared, EvaluationOut):
        return prepared
    ctx = CallContext(
        request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=prepared.attempt.student_id
    )
    outcome = service.run(llm_gateway(request), ctx, prepared)
    with sessions() as s:
        return service.record(s, principal, prepared, outcome, now=datetime.now(UTC))


@router.get("/evaluations/review-queue", response_model=list[ReviewItemOut])  # before /{evaluation_id}
def get_review_queue(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[ReviewItemOut]:
    sid = resolve_student_id(principal, student_id, scope="assessments")
    return service.review_queue(s, principal, student_id=sid)


@router.get("/evaluations/autopsies", response_model=list[AutopsyEntryOut])  # before /{evaluation_id}
def get_autopsies(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> list[AutopsyEntryOut]:
    sid = resolve_student_id(principal, student_id, scope="assessments")
    return service.list_autopsies(s, principal, student_id=sid, subject_id=subject_id)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: UUID, principal: PrincipalDep, s: DbDep) -> EvaluationOut:
    return service.get_evaluation(s, principal, evaluation_id)


@router.post("/evaluations/{evaluation_id}/autopsy", response_model=EvaluationOut)
def record_autopsy(evaluation_id: UUID, body: AutopsyIn, principal: PrincipalDep, s: DbDep) -> EvaluationOut:
    return service.record_autopsy(s, principal, evaluation_id, body, now=datetime.now(UTC))


@router.get("/evaluations/{evaluation_id}/examiner-insights", response_model=ExaminerInsightsOut)
def get_examiner_insights(evaluation_id: UUID, principal: PrincipalDep, s: DbDep) -> ExaminerInsightsOut:
    return service.examiner_insights(s, principal, evaluation_id)


@router.post("/evaluations/{evaluation_id}/override", response_model=EvaluationOut)
def override_evaluation(evaluation_id: UUID, body: OverrideIn, principal: PrincipalDep, s: DbDep) -> EvaluationOut:
    return service.override(s, principal, evaluation_id, body, now=datetime.now(UTC))
