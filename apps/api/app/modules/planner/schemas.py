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
    # True while the item is on a topic with questions and she has not answered one today: Done waits for that.
    needs_answer: bool = False


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


class TomorrowTopicOut(BaseModel):
    """A topic tomorrow's set would start from, chosen by the same rule over her record as it stands now."""

    subject_id: UUID
    subject_name: str
    objective_id: UUID
    objective_code: str
    objective_statement: str
    reason_code: str
    reason: str


class SessionDoorOut(BaseModel):
    """One way into today's work, sized to the time she has (docs/GO-LIVE-ENGAGEMENT.md F2).

    `minutes` is computed from the door's own content — about a minute a mark for questions, and for `deep` the
    topic page's own estimate of its next unfinished part — so it is what the work actually takes, not the size
    the door aims at. A closed door carries `closed_reason` and nothing to do.
    """

    key: Literal["quick", "today", "deep"]
    text: str  # what this door is, from reasons.yaml
    minutes: int
    questions: int
    objective_id: UUID | None = None  # `deep`: the topic it opens
    objective_code: str | None = None
    objective_statement: str | None = None
    parts: list[str] = []  # `deep`: the part this door starts with, then the parts after it on that page
    open: bool = True
    closed_reason: str | None = None


class DailyPracticeOut(BaseModel):
    practice_date: date
    rule_version: str
    items: list[DailyItemOut]
    done: int
    total: int
    notice: str | None = None
    # The topics tomorrow would start from: computed only once today's set is finished, since that is the only place
    # it is shown. Empty while there is still something to do today, and empty when nothing is waiting.
    tomorrow: list[TomorrowTopicOut] = []
    # The three ways into today's work, always all three, each either open with its real minutes or closed with
    # the reason why.
    doors: list[SessionDoorOut] = []
    # Time today, from her records: minutes spent answering in Scholr (timed by the answer box), the minutes today's
    # plan has room for (from her availability in the household seed, less commitments), and the minutes of external
    # classes and homework she recorded for today. Nothing is estimated.
    answering_minutes: int = 0
    planned_minutes: int | None = None
    external_minutes: int = 0
