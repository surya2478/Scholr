from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DbDep, PrincipalDep
from app.core.errors import not_found
from app.modules.curriculum import crucible, service
from app.modules.curriculum.schemas import (
    ObjectiveDetailOut,
    RelatedObjectiveOut,
    SubjectOut,
    SubjectTreeOut,
)
from app.modules.mastery import service as mastery
from app.modules.subjects import service as subjects

router = APIRouter(tags=["curriculum"])


@router.get("/subjects", response_model=list[SubjectOut])
def get_subjects(s: DbDep) -> list[SubjectOut]:
    return service.list_subjects(s)


@router.get("/subjects/{subject_id}/tree", response_model=SubjectTreeOut)
def get_subject_tree(subject_id: UUID, s: DbDep) -> SubjectTreeOut:
    tree = service.subject_tree(s, subject_id)
    if tree is None:
        raise not_found("subject")
    return tree


@router.get("/objectives/{objective_id}", response_model=ObjectiveDetailOut)
def get_objective(objective_id: UUID, s: DbDep) -> ObjectiveDetailOut:
    detail = service.objective_detail(s, objective_id)
    if detail is None:
        raise not_found("objective")
    return detail


@router.get("/objectives/{objective_id}/related", response_model=list[RelatedObjectiveOut])
def get_related_objectives(objective_id: UUID, principal: PrincipalDep, s: DbDep) -> list[RelatedObjectiveOut]:
    """What this objective shares with other subjects, and how she stands on each."""
    related = service.related_across_subjects(s, objective_id)
    levels: dict[UUID, int] = {}
    if principal.student_id is not None:
        levels = {row.objective_id: row.level for row in mastery.list_mastery(s, student_id=principal.student_id)}
    out = []
    for row in related:
        try:
            practicable = subjects.config_for(row.subject_code).taught_here
        except subjects.SubjectConfigError:
            practicable = False
        out.append(
            RelatedObjectiveOut(
                objective_id=row.objective_id,
                objective_code=row.objective_code,
                objective_statement=row.objective_statement,
                subject_id=row.subject_id,
                subject_name=row.subject_name,
                practicable=practicable,
                concept=row.concept_name,
                note=row.concept_note,
                mastery_level=levels.get(row.objective_id),
            )
        )
    return out


@router.get("/curriculum/crucible", response_model=list[crucible.CrucibleTopic])
def list_crucible_debates(principal: PrincipalDep, syllabus_unit: str | None = None) -> list[crucible.CrucibleTopic]:
    """Retrieve multi-perspective roundtable debates for Sociology 0495."""
    return crucible.list_crucible_topics(syllabus_unit=syllabus_unit)
