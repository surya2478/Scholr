from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.critic import service
from app.modules.critic.schemas import CriticOut

router = APIRouter(tags=["critic"])


@router.get("/study-patterns", response_model=CriticOut)
def get_study_patterns(
    principal: PrincipalDep,
    s: DbDep,
    student_id: UUID | None = None,
    # The student may read the guardian's wording of the same observation, and vice versa (AC-C3).
    audience: Annotated[str | None, Query(pattern="^(student|guardian)$")] = None,
) -> CriticOut:
    sid = resolve_student_id(principal, student_id, scope=service.SCOPE)
    return service.critique(s, principal, student_id=sid, now=datetime.now(UTC), audience=audience)
