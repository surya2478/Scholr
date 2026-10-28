"""Curriculum reads: subjects, topic trees, objectives. Curriculum rows are not student data."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import CONTENT_DIR
from app.modules.curriculum.models import (
    Concept,
    ConceptPrerequisite,
    ExamComponent,
    LearningObjective,
    ObjectiveConcept,
    Skill,
    Subject,
    Syllabus,
    Topic,
)
from app.modules.curriculum.schemas import (
    ComponentOut,
    ObjectiveDetailOut,
    ObjectiveOut,
    SubjectOut,
    SubjectTreeOut,
    TopicNode,
    TopicRef,
)
from app.modules.subjects import service as subjects

_CODE_PART = re.compile(r"\d+|[^\d.]+")
CURRICULUM_DIR = CONTENT_DIR / "curriculum"


def code_sort_key(code: str) -> tuple[tuple[int, int | str], ...]:
    """Natural order for codes such as 1.2 < 1.10 and U2 < U10."""
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in _CODE_PART.findall(code))


@dataclass(frozen=True)
class SubjectSummary:
    id: UUID
    code: str
    name: str


def list_subject_summaries(s: Session) -> list[SubjectSummary]:
    """Every subject row, id/code/name only. Curriculum rows are not student data."""
    rows = s.execute(select(Subject.id, Subject.code, Subject.name).order_by(Subject.code)).all()
    return [SubjectSummary(*row) for row in rows]


def subject_summaries(s: Session, subject_ids: Sequence[UUID]) -> dict[UUID, SubjectSummary]:
    if not subject_ids:
        return {}
    rows = s.execute(select(Subject.id, Subject.code, Subject.name).where(Subject.id.in_(list(subject_ids)))).all()
    return {row[0]: SubjectSummary(*row) for row in rows}


@dataclass(frozen=True)
class ObjectiveSummary:
    id: UUID
    code: str
    statement: str
    topic_id: UUID
    subject_id: UUID


def objective_summaries(s: Session, objective_ids: Sequence[UUID]) -> dict[UUID, ObjectiveSummary]:
    if not objective_ids:
        return {}
    rows = s.execute(
        select(
            LearningObjective.id,
            LearningObjective.code,
            LearningObjective.statement,
            LearningObjective.topic_id,
            Topic.subject_id,
        )
        .join(Topic, Topic.id == LearningObjective.topic_id)
        .where(LearningObjective.id.in_(list(objective_ids)))
    ).all()
    return {row[0]: ObjectiveSummary(*row) for row in rows}


def _stage(subject_code: str) -> str:
    try:
        return subjects.config_for(subject_code).stage
    except subjects.SubjectConfigError:
        return "taught"


def _subject_out(subject: Subject, syllabus: Syllabus | None, components: list[ExamComponent]) -> SubjectOut:
    return SubjectOut(
        id=subject.id,
        code=subject.code,
        name=subject.name,
        stage=(stage := _stage(subject.code)),
        taught_here=stage == "taught",
        syllabus_code=syllabus.code if syllabus else None,
        syllabus_title=syllabus.title if syllabus else None,
        syllabus_version=syllabus.version if syllabus else None,
        verification_status=syllabus.verification_status if syllabus else None,
        components=[ComponentOut.model_validate(c) for c in sorted(components, key=lambda c: code_sort_key(c.code))],
    )


def _subjects(s: Session, subject_id: UUID | None = None) -> list[SubjectOut]:
    query = select(Subject, Syllabus).outerjoin(Syllabus, Syllabus.id == Subject.syllabus_id).order_by(Subject.name)
    if subject_id is not None:
        query = query.where(Subject.id == subject_id)
    rows = s.execute(query).all()
    syllabus_ids = [syl.id for _, syl in rows if syl is not None]
    components: dict[UUID, list[ExamComponent]] = defaultdict(list)
    if syllabus_ids:
        for comp in s.scalars(select(ExamComponent).where(ExamComponent.syllabus_id.in_(syllabus_ids))):
            components[comp.syllabus_id].append(comp)
    return [_subject_out(subj, syl, components[syl.id] if syl else []) for subj, syl in rows]


def exam_seconds_per_mark(s: Session, subject_ids: Sequence[UUID]) -> dict[UUID, float]:
    """The time her papers allow per mark: all the syllabus's components' minutes over their marks. A subject with no
    timed component is left out, and nothing is guessed for it."""
    if not subject_ids:
        return {}
    rows = s.execute(
        select(Subject.id, func.sum(ExamComponent.duration_min), func.sum(ExamComponent.marks))
        .join(ExamComponent, ExamComponent.syllabus_id == Subject.syllabus_id)
        .where(
            Subject.id.in_(list(subject_ids)),
            ExamComponent.duration_min.is_not(None),
            ExamComponent.marks.is_not(None),
        )
        .group_by(Subject.id)
    ).all()
    return {sid: minutes * 60 / marks for sid, minutes, marks in rows if minutes and marks}


def list_subjects(s: Session) -> list[SubjectOut]:
    return _subjects(s)


def subject_tree(s: Session, subject_id: UUID) -> SubjectTreeOut | None:
    found = _subjects(s, subject_id)
    if not found:
        return None
    topics = s.scalars(
        select(Topic).where(Topic.subject_id == subject_id).order_by(Topic.depth, Topic.position, Topic.code)
    ).all()
    objectives: dict[UUID, list[ObjectiveOut]] = defaultdict(list)
    for obj in s.scalars(
        select(LearningObjective)
        .join(Topic, Topic.id == LearningObjective.topic_id)
        .where(Topic.subject_id == subject_id)
    ):
        objectives[obj.topic_id].append(ObjectiveOut.model_validate(obj))

    nodes: dict[UUID, TopicNode] = {}
    roots: list[TopicNode] = []
    for topic in topics:  # ordered by depth, so a parent is always built before its children
        node = TopicNode(
            id=topic.id,
            code=topic.code,
            name=topic.name,
            depth=topic.depth,
            verification_status=topic.verification_status,
            objectives=sorted(objectives[topic.id], key=lambda o: code_sort_key(o.code)),
        )
        nodes[topic.id] = node
        parent = nodes.get(topic.parent_id) if topic.parent_id else None
        (parent.children if parent else roots).append(node)
    return SubjectTreeOut(subject=found[0], topics=roots)


def objectives_by_code(s: Session, subject_id: UUID) -> dict[str, tuple[UUID, UUID]]:
    """Objective code -> (objective id, topic id) for one subject."""
    rows = s.execute(
        select(LearningObjective.code, LearningObjective.id, LearningObjective.topic_id)
        .join(Topic, Topic.id == LearningObjective.topic_id)
        .where(Topic.subject_id == subject_id)
    ).all()
    return {code: (oid, tid) for code, oid, tid in rows}


@lru_cache
def objective_start_pages(subject_code: str) -> dict[str, int]:
    """Printed course-textbook page where each objective's section starts (``page`` in content/curriculum/*.yaml)."""
    for path in sorted(CURRICULUM_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if (data.get("subject") or {}).get("code") != subject_code:
            continue
        pages: dict[str, int] = {}
        _collect_start_pages(data.get("topics"), pages)
        return pages
    return {}


def _collect_start_pages(topics: list[dict[str, Any]] | None, pages: dict[str, int]) -> None:
    for code, page in _section_starts(topics):
        pages.setdefault(code, page)  # the first section, in the order the file lists them


def _section_starts(topics: list[dict[str, Any]] | None) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for topic in topics or []:
        for objective in topic.get("objectives") or []:
            code = str(objective["code"])
            if isinstance(objective.get("page"), int):
                found.append((code, int(objective["page"])))
            found.extend((code, int(p)) for p in objective.get("pages") or [] if isinstance(p, int))
        found.extend(_section_starts(topic.get("children")))
    return found


def objective_section_starts(subject_code: str) -> list[tuple[int, str]]:
    """Every (printed page, objective code) where a course-book section on an objective starts, page order.

    A book that does not follow the syllabus order covers one objective in several places; such an objective
    lists them all (``pages: [3, 9, 59]`` in content/curriculum/*.yaml) so each page is tagged to the objective
    it is really about, not to whichever objective happened to start before it.
    """
    for path in sorted(CURRICULUM_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if (data.get("subject") or {}).get("code") == subject_code:
            return sorted((page, code) for code, page in _section_starts(data.get("topics")))
    return []


def skills_by_code(s: Session, subject_id: UUID) -> dict[str, tuple[UUID, str]]:
    """Skill code -> (skill id, name) for one subject (e.g. assessment objectives AO1-AO3)."""
    rows = s.execute(select(Skill.code, Skill.id, Skill.name).where(Skill.subject_id == subject_id)).all()
    return {code: (sid, name) for code, sid, name in rows}


def objective_counts(s: Session, subject_ids: Sequence[UUID]) -> dict[UUID, int]:
    if not subject_ids:
        return {}
    rows = s.execute(
        select(Topic.subject_id, func.count(LearningObjective.id))
        .join(LearningObjective, LearningObjective.topic_id == Topic.id)
        .where(Topic.subject_id.in_(list(subject_ids)))
        .group_by(Topic.subject_id)
    ).all()
    return {subject_id: count for subject_id, count in rows}


def objectives_under_topics(s: Session, topic_ids: Sequence[UUID]) -> list[ObjectiveSummary]:
    """Objectives of the given topics and all their descendant topics (a teaching-plan unit covers its chapters)."""
    wanted = set(topic_ids)
    if not wanted:
        return []
    frontier = set(wanted)
    while frontier:
        children = set(s.scalars(select(Topic.id).where(Topic.parent_id.in_(list(frontier))))) - wanted
        wanted |= children
        frontier = children
    ids = list(s.scalars(select(LearningObjective.id).where(LearningObjective.topic_id.in_(list(wanted)))))
    return list(objective_summaries(s, ids).values())


def objective_detail(s: Session, objective_id: UUID) -> ObjectiveDetailOut | None:
    obj = s.get(LearningObjective, objective_id)
    if obj is None:
        return None
    path: list[TopicRef] = []
    topic = s.get(Topic, obj.topic_id)
    subject_id = topic.subject_id if topic else None
    while topic is not None:
        path.insert(0, TopicRef(id=topic.id, code=topic.code, name=topic.name))
        topic = s.get(Topic, topic.parent_id) if topic.parent_id else None
    subject = s.get(Subject, subject_id) if subject_id else None
    if subject is None:
        return None
    return ObjectiveDetailOut(
        **ObjectiveOut.model_validate(obj).model_dump(),
        subject_id=subject.id,
        subject_code=subject.code,
        topic_path=path,
    )


@dataclass(frozen=True)
class ConceptView:
    id: UUID
    name: str
    description: str | None
    note: str | None


def concept_views(s: Session, concept_ids: Sequence[UUID]) -> dict[UUID, ConceptView]:
    if not concept_ids:
        return {}
    rows = s.execute(
        select(Concept.id, Concept.name, Concept.description, Concept.note).where(Concept.id.in_(list(concept_ids)))
    ).all()
    return {row[0]: ConceptView(*row) for row in rows}


def concepts_of_objectives(s: Session, objective_ids: Sequence[UUID]) -> dict[UUID, tuple[UUID, ...]]:
    """Objective id -> the concepts it teaches."""
    if not objective_ids:
        return {}
    rows = s.execute(
        select(ObjectiveConcept.objective_id, ObjectiveConcept.concept_id)
        .where(ObjectiveConcept.objective_id.in_(list(objective_ids)))
        .order_by(ObjectiveConcept.concept_id)
    ).all()
    grouped: dict[UUID, list[UUID]] = defaultdict(list)
    for objective_id, concept_id in rows:
        grouped[objective_id].append(concept_id)
    return {k: tuple(v) for k, v in grouped.items()}


def objectives_of_concepts(
    s: Session, concept_ids: Sequence[UUID], *, subject_ids: Sequence[UUID] | None = None
) -> dict[UUID, tuple[UUID, ...]]:
    """Concept id -> the objectives that teach it, optionally limited to some subjects."""
    if not concept_ids:
        return {}
    query = (
        select(ObjectiveConcept.concept_id, ObjectiveConcept.objective_id)
        .join(LearningObjective, LearningObjective.id == ObjectiveConcept.objective_id)
        .join(Topic, Topic.id == LearningObjective.topic_id)
        .where(ObjectiveConcept.concept_id.in_(list(concept_ids)))
        .order_by(ObjectiveConcept.objective_id)
    )
    if subject_ids is not None:
        query = query.where(Topic.subject_id.in_(list(subject_ids)))
    grouped: dict[UUID, list[UUID]] = defaultdict(list)
    for concept_id, objective_id in s.execute(query).all():
        grouped[concept_id].append(objective_id)
    return {k: tuple(v) for k, v in grouped.items()}


def prerequisites_of_concepts(s: Session, concept_ids: Sequence[UUID]) -> dict[UUID, tuple[tuple[UUID, float], ...]]:
    """Concept id -> (prerequisite concept id, strength). One hop; the caller walks as deep as it needs."""
    if not concept_ids:
        return {}
    rows = s.execute(
        select(ConceptPrerequisite.concept_id, ConceptPrerequisite.prerequisite_id, ConceptPrerequisite.strength)
        .where(ConceptPrerequisite.concept_id.in_(list(concept_ids)))
        .order_by(ConceptPrerequisite.prerequisite_id)
    ).all()
    grouped: dict[UUID, list[tuple[UUID, float]]] = defaultdict(list)
    for concept_id, prerequisite_id, strength in rows:
        grouped[concept_id].append((prerequisite_id, float(strength)))
    return {k: tuple(v) for k, v in grouped.items()}


@dataclass(frozen=True)
class RelatedObjective:
    """An objective in another subject that rests on the same concept."""

    objective_id: UUID
    objective_code: str
    objective_statement: str
    subject_id: UUID
    subject_code: str
    subject_name: str
    concept_id: UUID
    concept_name: str
    concept_note: str | None


def related_across_subjects(s: Session, objective_id: UUID) -> list[RelatedObjective]:
    """Objectives in *other* subjects sharing a concept with this one (AC-G2).

    One hop only: a shared concept is a claim that the same idea is being used, which is worth saying. A
    prerequisite two steps away in another subject is a much weaker claim and is left unsaid.
    """
    concept_ids = concepts_of_objectives(s, [objective_id]).get(objective_id, ())
    if not concept_ids:
        return []
    summaries = objective_summaries(s, [objective_id])
    if objective_id not in summaries:
        return []
    own_subject = summaries[objective_id].subject_id

    by_concept = objectives_of_concepts(s, list(concept_ids))
    candidate_ids = {oid for ids in by_concept.values() for oid in ids} - {objective_id}
    candidates = objective_summaries(s, list(candidate_ids))
    subjects = subject_summaries(s, [o.subject_id for o in candidates.values()])
    concepts = concept_views(s, list(concept_ids))

    found: list[RelatedObjective] = []
    for concept_id, objective_ids in by_concept.items():
        for other_id in objective_ids:
            other = candidates.get(other_id)
            if other is None or other.subject_id == own_subject:
                continue
            subject = subjects.get(other.subject_id)
            concept = concepts.get(concept_id)
            if subject is None or concept is None:
                continue
            found.append(
                RelatedObjective(
                    objective_id=other.id,
                    objective_code=other.code,
                    objective_statement=other.statement,
                    subject_id=subject.id,
                    subject_code=subject.code,
                    subject_name=subject.name,
                    concept_id=concept.id,
                    concept_name=concept.name,
                    concept_note=concept.note,
                )
            )
    found.sort(key=lambda r: (r.subject_name, code_sort_key(r.objective_code)))
    return found
