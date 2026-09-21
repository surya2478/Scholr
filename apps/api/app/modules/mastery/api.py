from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.rbac import resolve_student_id
from app.modules.mastery import service
from app.modules.mastery.schemas import EvidenceOut, MasteryOut, SkillOut

router = APIRouter(tags=["mastery"])


@router.get("/mastery", response_model=list[MasteryOut])
def get_mastery(
    principal: PrincipalDep, s: DbDep, subject_id: UUID | None = None, student_id: UUID | None = None
) -> list[MasteryOut]:
    sid = resolve_student_id(principal, student_id, scope="mastery")
    return service.list_mastery(s, student_id=sid, subject_id=subject_id)


@router.get("/skills", response_model=list[SkillOut])
def get_skills(
    principal: PrincipalDep, s: DbDep, subject_id: UUID | None = None, student_id: UUID | None = None
) -> list[SkillOut]:
    sid = resolve_student_id(principal, student_id, scope="mastery")
    return service.list_skills(s, student_id=sid, subject_id=subject_id)


@router.get("/mastery/{objective_id}/evidence", response_model=list[EvidenceOut])
def get_mastery_evidence(
    objective_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> list[EvidenceOut]:
    sid = resolve_student_id(principal, student_id, scope="mastery")
    return service.evidence_for(s, student_id=sid, objective_id=objective_id)
