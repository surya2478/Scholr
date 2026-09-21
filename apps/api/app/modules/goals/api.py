from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.goals import service
from app.modules.goals.schemas import GoalIn, GoalOut

router = APIRouter(tags=["goals"])


@router.get("/goals", response_model=list[GoalOut])
def get_goals(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[GoalOut]:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    service.settle_achieved(s, sid, now=datetime.now(UTC))
    return service.list_goals(s, principal, student_id=sid, now=datetime.now(UTC))


@router.post("/goals", response_model=GoalOut, status_code=201)
def post_goal(body: GoalIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> GoalOut:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.create_goal(s, principal, student_id=sid, body=body, now=datetime.now(UTC))


@router.post("/goals/{goal_id}/agree", response_model=GoalOut)
def post_agree(goal_id: UUID, principal: PrincipalDep, s: DbDep) -> GoalOut:
    return service.agree(s, principal, goal_id, now=datetime.now(UTC))


@router.post("/goals/{goal_id}/drop", response_model=GoalOut)
def post_drop(goal_id: UUID, principal: PrincipalDep, s: DbDep) -> GoalOut:
    return service.drop(s, principal, goal_id, now=datetime.now(UTC))
