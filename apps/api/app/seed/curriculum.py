"""Idempotent curriculum seed from content/curriculum/*.yaml.

Usage: uv run python -m app.seed.curriculum ../../content/curriculum/igcse-maths-0580.yaml [...]

YAML shape:
  curriculum: {code, name}
  path: {code, name}
  syllabus: {code, title, version, tiers, first_exam_year?, last_exam_year?, verification_status, source_note}
  subject: {code, name, config_key}
  components: [{code, name, tier?, duration_min?, marks?, calculator_allowed?, structure_note?}]
  skills: [{code, name, kind}]
  topics:
    - code, name, syllabus_ref?, children: [{code, name, objectives: [{code, statement, tier, syllabus_ref?}]}]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.modules.curriculum.models import (
    Curriculum,
    ExamComponent,
    LearningObjective,
    LearningPath,
    Skill,
    Subject,
    Syllabus,
    Topic,
)

Verification = Literal["unverified", "verified"]


class ObjectiveIn(BaseModel):
    code: str
    statement: str
    tier: Literal["core", "extended", "all"] = "all"
    syllabus_ref: str | None = None


class TopicIn(BaseModel):
    code: str
    name: str
    syllabus_ref: str | None = None
    objectives: list[ObjectiveIn] = Field(default_factory=list)
    children: list[TopicIn] = Field(default_factory=list)


class ComponentIn(BaseModel):
    code: str
    name: str
    tier: str | None = None
    duration_min: int | None = None
    marks: int | None = None
    calculator_allowed: bool | None = None
    structure_note: str | None = None


class SkillIn(BaseModel):
    code: str
    name: str
    kind: Literal["assessment_objective", "process"] = "assessment_objective"


class SyllabusIn(BaseModel):
    code: str
    title: str
    version: str
    tiers: list[str] = Field(default_factory=list)
    first_exam_year: int | None = None
    last_exam_year: int | None = None
    verification_status: Verification = "unverified"
    source_note: str | None = None


class CurriculumFile(BaseModel):
    curriculum: dict[str, str]
    path: dict[str, str]
    syllabus: SyllabusIn
    subject: dict[str, str]
    components: list[ComponentIn] = Field(default_factory=list)
    skills: list[SkillIn] = Field(default_factory=list)
    topics: list[TopicIn]


def _get_or_create(s: Session, model: type[Any], lookup: dict[str, Any], values: dict[str, Any]) -> Any:
    row = s.scalar(select(model).filter_by(**lookup))
    if row is None:
        row = model(**lookup, **values)
        s.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    s.flush()
    return row


def _seed_topic(
    s: Session,
    subject_id: UUID,
    topic: TopicIn,
    parent_id: UUID | None,
    depth: int,
    position: int,
    verification: Verification,
    counts: dict[str, int],
) -> None:
    row = _get_or_create(
        s,
        Topic,
        {"subject_id": subject_id, "code": topic.code},
        {
            "name": topic.name,
            "parent_id": parent_id,
            "depth": depth,
            "position": position,
            "syllabus_ref": topic.syllabus_ref,
            "verification_status": verification,
        },
    )
    counts["topics"] += 1
    for obj in topic.objectives:
        _get_or_create(
            s,
            LearningObjective,
            {"topic_id": row.id, "code": obj.code},
            {
                "statement": obj.statement,
                "tier": obj.tier,
                "syllabus_ref": obj.syllabus_ref,
                "verification_status": verification,
            },
        )
        counts["objectives"] += 1
    for i, child in enumerate(topic.children):
        _seed_topic(s, subject_id, child, row.id, depth + 1, i, verification, counts)


def seed_curriculum(s: Session, data: CurriculumFile) -> dict[str, int]:
    curriculum = _get_or_create(s, Curriculum, {"code": data.curriculum["code"]}, {"name": data.curriculum["name"]})
    path = _get_or_create(s, LearningPath, {"code": data.path["code"]}, {"name": data.path["name"]})
    syl = data.syllabus
    syllabus = _get_or_create(
        s,
        Syllabus,
        {"curriculum_id": curriculum.id, "code": syl.code, "version": syl.version},
        syl.model_dump(exclude={"code", "version"}),
    )
    subject = _get_or_create(
        s,
        Subject,
        {"code": data.subject["code"]},
        {
            "name": data.subject["name"],
            "config_key": data.subject["config_key"],
            "path_id": path.id,
            "syllabus_id": syllabus.id,
        },
    )
    for comp in data.components:
        _get_or_create(
            s,
            ExamComponent,
            {"syllabus_id": syllabus.id, "code": comp.code},
            {**comp.model_dump(exclude={"code"}), "verification_status": syl.verification_status},
        )
    for skill in data.skills:
        _get_or_create(s, Skill, {"subject_id": subject.id, "code": skill.code}, skill.model_dump(exclude={"code"}))
    counts = {"topics": 0, "objectives": 0}
    for i, topic in enumerate(data.topics):
        _seed_topic(s, subject.id, topic, None, 0, i, syl.verification_status, counts)
    return {"components": len(data.components), "skills": len(data.skills), **counts}


def load_file(path: Path) -> CurriculumFile:
    return CurriculumFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit("usage: python -m app.seed.curriculum <file.yaml> [...]")
    for arg in argv[1:]:
        data = load_file(Path(arg))
        with session_scope(user_id=None, role="system") as s:
            print(arg, seed_curriculum(s, data))


if __name__ == "__main__":
    main(sys.argv)
