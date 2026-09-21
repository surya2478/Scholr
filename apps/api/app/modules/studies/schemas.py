from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PairCreate(BaseModel):
    """One matched topic pair: the arms come from a recorded coin flip (PHASE-1 §5)."""

    model_config = ConfigDict(extra="forbid")

    subject_id: UUID
    pair_code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    app_objective_ids: list[UUID] = Field(min_length=1, max_length=20)
    control_objective_ids: list[UUID] = Field(min_length=1, max_length=20)
    assignment_method: str = Field(min_length=3, max_length=500, description="e.g. coin flip recorded by parent")
    assigned_at: datetime | None = None


class AssignmentOut(BaseModel):
    id: UUID
    subject_id: UUID
    pair_code: str
    arm: str
    objective_ids: list[UUID]
    objective_codes: list[str]
    assignment_method: str
    assigned_at: datetime
    crossover_at: datetime | None


class TopicScoreOut(BaseModel):
    awarded: float
    available: int
    ratio: float
    provisional: bool


class ArmResultOut(BaseModel):
    pair_code: str
    arm: str
    objective_codes: list[str]
    baseline: TopicScoreOut | None
    post: TopicScoreOut | None
    retention: TopicScoreOut | None
    gain: float | None
    retention_ratio: float | None
    eligible: bool | None
    overlapping_items: int


class FormOut(BaseModel):
    assessment_id: UUID
    kind: str
    form_code: str | None
    submitted_at: datetime


class StudyResultsOut(BaseModel):
    student_id: UUID
    subject_id: UUID
    generated_at: datetime
    rule_version: str
    forms: list[FormOut]
    arms: list[ArmResultOut]
    decision: str  # pending | go_candidate | iterate | no_gain
    reasons: list[str]
    provisional: bool
    sessions_per_week: float | None
    app_hours: float
    mean_gain_app: float | None
    mean_gain_control: float | None
    gain_difference: float | None
    mean_retention_app: float | None
    mean_retention_control: float | None
    learning_per_hour: float | None
