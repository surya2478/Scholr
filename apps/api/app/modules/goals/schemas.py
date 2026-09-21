from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Measure = Literal["topics_secure", "active_days_per_week", "answers_without_help", "open_mistakes"]


class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=3, max_length=300)
    measure: Measure
    target_value: float = Field(ge=0, le=10000)
    subject_id: UUID | None = None
    target_date: date | None = None


class GoalOut(BaseModel):
    id: UUID
    statement: str
    measure: str
    measure_label: str
    unit: str
    help: str
    subject_id: UUID | None
    subject_name: str | None
    status: str
    # Who put it forward, and whether the student has agreed to it. A goal a parent proposes is not
    # active until she does (AC-G1).
    proposed_by_role: str
    agreed: bool
    target_date: date | None
    current: float
    target: float
    baseline: float | None
    direction: str
    # 0..1 of the way from the baseline to the target; None when there was no baseline to measure from.
    share: float | None
    reached: bool
    days_left: int | None
    rule_version: str
