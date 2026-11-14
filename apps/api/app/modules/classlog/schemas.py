from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChapterOut(BaseModel):
    topic_id: UUID
    code: str
    name: str


class LoggedOut(ChapterOut):
    entry_id: UUID  # the teaching-plan entry it made; DELETE /teaching-plan/{id} undoes a wrong tap
    # The first topic in the chapter she is not yet secure in: where "lock it in tonight" opens.
    next_objective_id: UUID | None
    next_objective_code: str | None


class ClassSubjectOut(BaseModel):
    subject_id: UUID
    subject_name: str
    logged: list[LoggedOut]  # what she tapped today
    suggestions: list[ChapterOut]  # the likeliest chapters, best first (classlog.service.suggest)
    others: list[ChapterOut]  # every other chapter, in syllabus order


class ClassCheckInOut(BaseModel):
    """What did class cover today? (docs/GO-LIVE-ENGAGEMENT.md F4)."""

    day: date
    school_day: bool
    subjects: list[ClassSubjectOut]


class ClassCheckInIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: UUID
    topic_id: UUID
