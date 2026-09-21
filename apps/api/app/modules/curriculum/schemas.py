from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    tier: str | None
    duration_min: int | None
    marks: int | None
    calculator_allowed: bool | None


class SubjectOut(BaseModel):
    id: UUID
    code: str
    name: str
    syllabus_code: str | None
    syllabus_title: str | None
    syllabus_version: str | None
    verification_status: str | None
    # How far Scholr has got with this subject: "taught" (full engine), "planned" (syllabus known, no
    # questions or marking yet) or "external" (learnt elsewhere). Surfaces read this instead of recognising
    # subject codes (subject_configs/*.yaml `stage`).
    stage: str = "taught"
    taught_here: bool = True
    components: list[ComponentOut] = Field(default_factory=list)


class ObjectiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    statement: str
    tier: str
    verification_status: str


class TopicNode(BaseModel):
    id: UUID
    code: str
    name: str
    depth: int
    verification_status: str
    objectives: list[ObjectiveOut] = Field(default_factory=list)
    children: list[TopicNode] = Field(default_factory=list)


class SubjectTreeOut(BaseModel):
    subject: SubjectOut
    topics: list[TopicNode]


class TopicRef(BaseModel):
    id: UUID
    code: str
    name: str


class ObjectiveDetailOut(ObjectiveOut):
    subject_id: UUID
    subject_code: str
    topic_path: list[TopicRef]


TopicNode.model_rebuild()


class RelatedObjectiveOut(BaseModel):
    """An objective in another subject built on the same concept (AC-G2)."""

    objective_id: UUID
    objective_code: str
    objective_statement: str
    subject_id: UUID
    subject_name: str
    # False when Scholr knows the subject's syllabus but cannot set work in it yet.
    practicable: bool
    # The shared idea. A link that cannot name one is not a relationship, it is a coincidence.
    concept: str
    note: str | None = None
    # What she has shown on the related objective, when there is anything to show.
    mastery_level: int | None = None
