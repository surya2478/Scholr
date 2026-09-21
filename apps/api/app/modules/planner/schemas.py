from __future__ import annotations

from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanItemOut(BaseModel):
    id: UUID
    position: int
    subject_id: UUID
    subject_name: str
    objective_id: UUID | None
    objective_code: str | None
    objective_statement: str | None
    kind: str
    est_minutes: int
    priority: float
    reason_code: str
    reason: str
    status: str


class TimelineBlockOut(BaseModel):
    """One row of My Day: a fixed commitment, or a plan item placed in the gaps around them."""

    kind: str  # "commitment", or the plan item's kind
    title: str
    detail: str | None
    minutes: int
    start: time | None  # None: no room in today's study window, so it has no set time
    end: time | None
    status: str | None  # plan item status; None for commitments
    plan_item_id: UUID | None


class DroppedOut(BaseModel):
    objective_code: str | None
    kind: str
    reason_code: str


class PlanOut(BaseModel):
    id: UUID
    plan_date: date
    capacity_minutes: int
    planned_minutes: int
    items: list[PlanItemOut]
    timeline: list[TimelineBlockOut]
    dropped: list[DroppedOut]
    notices: list[str]


class PlanItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["in_progress", "completed", "skipped"]


class DailyItemOut(BaseModel):
    """One question in today's practice set, with why it was chosen and how she has done on it today."""

    item_id: UUID
    subject_id: UUID
    subject_name: str
    objective_id: UUID
    objective_code: str
    objective_statement: str
    source_ref: str | None
    label: str  # what she sees: "June 2025 · Paper 21 · Q17(b)(ii)", or "Practice question"
    marks: int
    reason_code: str
    reason: str
    status: Literal["to_do", "answered", "marked", "provisional"]
    evaluation_id: UUID | None = None
    marks_awarded: float | None = None


class DailyPracticeOut(BaseModel):
    practice_date: date
    rule_version: str
    items: list[DailyItemOut]
    done: int
    total: int
    notice: str | None = None
