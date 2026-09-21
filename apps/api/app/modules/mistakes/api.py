from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.mistakes import service
from app.modules.mistakes.schemas import MistakeOut

router = APIRouter(tags=["mistakes"])


@router.get("/mistakes", response_model=list[MistakeOut])
def get_mistakes(
    principal: PrincipalDep,
    s: DbDep,
    subject_id: UUID | None = None,
    status: Literal["open", "improving", "resolved"] | None = None,
    student_id: UUID | None = None,
) -> list[MistakeOut]:
    sid = resolve_student_id(principal, student_id, scope="progress")
    return service.list_mistakes(s, student_id=sid, subject_id=subject_id, status=status)
