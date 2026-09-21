from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Kind = Literal["class", "test", "homework", "practice"]


class ExternalTrainingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: UUID
    kind: Kind = "class"
    title: str = Field(min_length=1, max_length=200)
    occurred_on: date
    duration_min: int | None = Field(default=None, ge=0, le=720)
    objective_ids: list[UUID] = Field(default_factory=list, max_length=40)
    weak_objective_ids: list[UUID] = Field(default_factory=list, max_length=40)
    score: float | None = Field(default=None, ge=0)
    max_score: float | None = Field(default=None, gt=0)
    questions_attempted: int | None = Field(default=None, ge=0, le=500)
    questions_missed: int | None = Field(default=None, ge=0, le=500)
    weaknesses: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _consistent(self) -> ExternalTrainingIn:
        if (self.score is None) != (self.max_score is None):
            raise ValueError("score and max_score must be given together")
        if self.score is not None and self.max_score is not None and self.score > self.max_score:
            raise ValueError("score exceeds max_score")
        if (
            self.questions_attempted is not None
            and self.questions_missed is not None
            and self.questions_missed > self.questions_attempted
        ):
            raise ValueError("questions_missed exceeds questions_attempted")
        if not set(self.weak_objective_ids) <= set(self.objective_ids):
            raise ValueError("weak_objective_ids must be among objective_ids")
        return self


class LessonRef(BaseModel):
    objective_id: UUID
    code: str
    title: str


class ExternalTrainingOut(BaseModel):
    id: UUID
    subject_id: UUID
    subject_name: str
    kind: Kind
    title: str
    occurred_on: date
    duration_min: int | None
    lessons: list[LessonRef]
    weak_lessons: list[LessonRef]
    score: float | None
    max_score: float | None
    questions_attempted: int | None
    questions_missed: int | None
    weaknesses: list[str]
    notes: str | None


class ReinforcementOut(BaseModel):
    """An objective in a subject Scholr teaches, suggested because an external class went badly."""

    objective_id: UUID
    objective_code: str
    objective_statement: str
    subject_id: UUID
    subject_name: str
    concept: str
    # 0 = the idea the class taught, 1+ = something it rests on.
    depth: int
    # False = Scholr knows this subject's syllabus but has no questions or marking for it yet, so the
    # suggestion is "revise this from your course book", not "practise this here".
    practicable: bool = True
    reason: str
    note: str | None = None
    priority: float


class LessonStandingOut(BaseModel):
    objective_id: UUID
    code: str
    title: str
    sessions: int
    last_seen_on: date
    accuracy: float | None  # 0..1 across logged scores, None when nothing was scored
    flagged: bool


class SubjectStandingOut(BaseModel):
    subject_id: UUID
    subject_name: str
    sessions: int
    minutes: int
    last_seen_on: date | None
    accuracy: float | None
    lessons_covered: int
    lessons_total: int
    # False = nothing in this course maps to a subject Scholr teaches yet, so it cannot suggest follow-up.
    traceable: bool = True
    weak_lessons: list[LessonStandingOut]


class ExternalSummaryOut(BaseModel):
    subjects: list[SubjectStandingOut]
    recent: list[ExternalTrainingOut]
    reinforcement: list[ReinforcementOut]
