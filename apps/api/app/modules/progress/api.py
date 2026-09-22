from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.progress import service
from app.modules.progress.schemas import (
    GuardianOverviewOut,
    MetacognitionOut,
    MonthlySummaryOut,
    ProgressSummaryOut,
    TrendsOut,
)

router = APIRouter(tags=["progress"])


@router.get("/progress/summary", response_model=ProgressSummaryOut)
def get_summary(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> ProgressSummaryOut:
    sid = resolve_student_id(principal, student_id, scope="progress")
    return service.summary(s, principal, student_id=sid, now=datetime.now(UTC))


@router.get("/progress/metacognition", response_model=MetacognitionOut)
def get_metacognition(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> MetacognitionOut:
    sid = resolve_student_id(principal, student_id, scope="progress")
    return service.metacognition(s, principal, student_id=sid, subject_id=subject_id)


@router.get("/guardian/students/{student_id}/overview", response_model=GuardianOverviewOut)
def get_guardian_overview(student_id: UUID, principal: PrincipalDep, s: DbDep) -> GuardianOverviewOut:
    return service.guardian_overview(s, principal, student_id=student_id, now=datetime.now(UTC))


@router.get("/guardian/students/{student_id}/monthly", response_model=MonthlySummaryOut)
def get_guardian_monthly(
    student_id: UUID,
    principal: PrincipalDep,
    s: DbDep,
    month: Annotated[str | None, Query(pattern=service.MONTH_PATTERN)] = None,
) -> MonthlySummaryOut:
    return service.guardian_monthly(s, principal, student_id=student_id, month=month, now=datetime.now(UTC))


@router.get("/guardian/students/{student_id}/trends", response_model=TrendsOut)
def get_guardian_trends(
    student_id: UUID,
    principal: PrincipalDep,
    s: DbDep,
    weeks: Annotated[int, Query(ge=2, le=26)] = service.TREND_WEEKS,
) -> TrendsOut:
    return service.guardian_trends(s, principal, student_id=student_id, weeks=weeks, now=datetime.now(UTC))
