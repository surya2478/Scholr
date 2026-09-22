from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Any

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


class MistakeNoteOut(BaseModel):
    category: str
    label: str
    severity: str
    description: str


class AnswerCheckOut(BaseModel):
    status: str
    detail: str


class EvaluationOut(BaseModel):
    id: UUID
    attempt_id: UUID
    status: str
    provisional: bool
    marks_awarded: float
    marks_available: float
    feedback: FeedbackOut
    final_answer_check: AnswerCheckOut | None
    awards: list[AwardOut] = Field(default_factory=list)
    mistakes: list[MistakeNoteOut] = Field(default_factory=list)
    created_at: datetime
    reviewed_at: datetime | None = None  # set when a parent/admin reviewed and overrode the marks


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
