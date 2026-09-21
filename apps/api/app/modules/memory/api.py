from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.memory import service
from app.modules.memory.schemas import MemoryOut

router = APIRouter(tags=["memory"])


@router.get("/memory", response_model=list[MemoryOut])
def get_memory(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    subject_id: UUID | None = None,
    include_superseded: bool = False,
) -> list[MemoryOut]:
    sid = resolve_student_id(principal, student_id, scope="memory")
    return service.list_memory(
        s, principal, student_id=sid, subject_id=subject_id, include_superseded=include_superseded
    )
