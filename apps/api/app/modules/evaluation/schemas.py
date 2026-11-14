from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AutopsyIn(BaseModel):
    category: str
    takeaway: str


class AutopsyEntryOut(BaseModel):
    evaluation_id: UUID
    attempt_id: UUID
    subject_id: UUID
    objective_code: str | None
    stem: str
    category: str
    takeaway: str
    marks_awarded: float
    marks_available: float
    recorded_at: datetime


class FeedbackOut(BaseModel):
    summary: str
    what_went_well: str | None
    next_step: str
    autopsy: dict[str, Any] | None = None


class AwardOut(BaseModel):
    code: str
    awarded: bool
    reason: str
    meaning: str | None = None  # what this kind of mark is for (mark_codes.py); None for a code it does not know


class SkillShownOut(BaseModel):
    """One assessment objective in a level-marked answer: whether the answer showed it, and its marks once final."""

    code: str  # "AO1"
    shown: bool
    marks: float | None = None  # None for the student while the mark is provisional (AC-E6)


class MistakeNoteOut(BaseModel):
    category: str
    label: str
    severity: str
    description: str


class AnswerCheckOut(BaseModel):
    status: str
    detail: str


class PendingCheckOut(BaseModel):
    """What she sees of a provisional mark (AC-E6): what her answer did and did not do, never a number.

    The points come from the mark-scheme marking itself. No mark, level or band total is shown, nothing here is
    read by mastery, and `who` says who will check it.
    """

    points_made: list[str] = Field(default_factory=list)
    points_missed: list[str] = Field(default_factory=list)
    who: str
    waiting_since: datetime
    check_at: datetime | None = None  # the next weekly check-in (improvement 9)
    overdue: bool = False  # a check-in has passed since it arrived and it is still waiting


class ReviewSlotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weekday: int = Field(ge=0, le=6)  # 0 = Monday
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # "18:00", her local time


class ReviewStatusOut(BaseModel):
    """The weekly check-in for marks waiting for a parent (improvement 9; GO-LIVE F12)."""

    weekday: int  # 0 = Monday
    time: str  # "18:00", the student's local time
    chosen: bool  # False while it is still the default (Sunday 18:00)
    next_check: datetime
    waiting: int
    oldest_waiting_since: datetime | None
    missed: bool  # a check-in passed while something was already waiting


class EvaluationOut(BaseModel):
    id: UUID
    attempt_id: UUID
    status: str
    provisional: bool
    # None for the student while the mark is provisional (AC-E6): she sees `pending` instead of a number.
    marks_awarded: float | None
    marks_available: float
    feedback: FeedbackOut
    final_answer_check: AnswerCheckOut | None
    awards: list[AwardOut] = Field(default_factory=list)
    mistakes: list[MistakeNoteOut] = Field(default_factory=list)
    created_at: datetime
    reviewed_at: datetime | None = None  # set when a parent/admin reviewed and overrode the marks
    pending: PendingCheckOut | None = None  # the student's view of a provisional mark
    # Mark-scheme literacy (improvement 6): when working earned a method mark that the answer alone would not have.
    method_note: str | None = None
    skills: list[SkillShownOut] = Field(default_factory=list)  # level-marked answers: the objectives it showed


class ReviewItemOut(BaseModel):
    """A provisional evaluation waiting for a human reviewer (guardian/admin only: includes the mark scheme)."""

    evaluation: EvaluationOut
    student_id: UUID
    subject_id: UUID
    source_ref: str | None
    context: str | None
    stem: str
    working: str | None
    final_answer: str | None
    mark_scheme: str
    confidence: float
    issues: list[str]


class OverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    marks_awarded: float = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)
