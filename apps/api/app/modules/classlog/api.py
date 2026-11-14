from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.classlog import service
from app.modules.classlog.schemas import ClassCheckInIn, ClassCheckInOut

router = APIRouter(tags=["classlog"])


@router.get("/class-check-in", response_model=ClassCheckInOut)
def get_class_check_in(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> ClassCheckInOut:
    """What did class cover today? Each school subject, what she tapped, and the likeliest chapters (F4)."""
    sid = resolve_student_id(principal, student_id, service.SCOPE)
    return service.today(s, principal, student_id=sid, now=datetime.now(UTC))


@router.post("/class-check-in", response_model=ClassCheckInOut, status_code=201)
def post_class_check_in(
    body: ClassCheckInIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> ClassCheckInOut:
    sid = resolve_student_id(principal, student_id, service.SCOPE)
    return service.log(s, principal, student_id=sid, body=body, now=datetime.now(UTC))
