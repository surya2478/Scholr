from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.planner import service
from app.modules.planner.schemas import DailyPracticeOut, PlanItemUpdate, PlanOut

router = APIRouter(tags=["planner"])


@router.get("/plan/today", response_model=PlanOut)
def get_today(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> PlanOut:
    sid = resolve_student_id(principal, student_id, scope="plans")
    return service.plan_today(s, principal, student_id=sid, now=datetime.now(UTC))


@router.post("/plan/regenerate", response_model=PlanOut)
def regenerate(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> PlanOut:
    sid = resolve_student_id(principal, student_id, scope="plans")
    return service.regenerate(s, principal, student_id=sid, now=datetime.now(UTC))


@router.patch("/plan/items/{item_id}", response_model=PlanOut)
def update_item(item_id: UUID, body: PlanItemUpdate, principal: PrincipalDep, s: DbDep) -> PlanOut:
    return service.update_item(s, principal, item_id, body.status, now=datetime.now(UTC))


@router.get("/practice/daily", response_model=DailyPracticeOut)
def get_daily_practice(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> DailyPracticeOut:
    sid = resolve_student_id(principal, student_id, scope="plans")
    return service.daily_practice(s, principal, student_id=sid, now=datetime.now(UTC))
