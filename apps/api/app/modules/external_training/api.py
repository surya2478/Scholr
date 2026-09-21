from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.external_training import service
from app.modules.external_training.schemas import ExternalSummaryOut, ExternalTrainingIn, ExternalTrainingOut
from app.modules.identity import service as identity
from app.tools.dates import local_date

router = APIRouter(tags=["external-training"])


def _today(s: DbDep, student_id: UUID) -> date:
    return local_date(datetime.now(UTC), identity.student_timezone(s, student_id))


@router.post("/external-training", response_model=ExternalTrainingOut, status_code=201)
def post_log(body: ExternalTrainingIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None):
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.record(s, principal, student_id=sid, body=body)


@router.get("/external-training", response_model=list[ExternalTrainingOut])
def get_logs(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = service.RECENT_LIMIT,
):
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.list_logs(s, principal, student_id=sid, limit=limit)


@router.get("/external-training/summary", response_model=ExternalSummaryOut)
def get_summary(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    weeks: Annotated[int, Query(ge=1, le=52)] = 12,
):
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.summary(s, principal, student_id=sid, today=_today(s, sid), weeks=weeks)
