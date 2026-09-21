from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.tools.dates import RecurrenceError, parse_rrule


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AvailabilityIn(_In):
    minutes: list[int] = Field(min_length=7, max_length=7, description="study minutes Monday..Sunday")

    @field_validator("minutes")
    @classmethod
    def _range(cls, value: list[int]) -> list[int]:
        if any(m < 0 or m > 720 for m in value):
            raise ValueError("each day must be between 0 and 720 minutes")
        return value


class AvailabilityOut(BaseModel):
    minutes: list[int]


class CommitmentIn(_In):
    kind: Literal["iit_class", "extracurricular", "school", "other"]
    title: str = Field(min_length=1, max_length=200)
    rrule: str = Field(max_length=300, description="e.g. FREQ=WEEKLY;BYDAY=MO,WE,FR")
    start_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration_min: int = Field(gt=0, le=720)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("rrule")
    @classmethod
    def _supported_rule(cls, value: str) -> str:
        try:
            parse_rrule(value)
        except RecurrenceError as exc:
            raise ValueError(str(exc)) from None
        return value.upper()


class CommitmentOut(BaseModel):
    id: UUID
    kind: str
    title: str
    rrule: str
    start_time: str | None
    duration_min: int
    notes: str | None


class TeachingEntryIn(_In):
    subject_id: UUID
    term: str = Field(max_length=32)
    label: str = Field(max_length=300)
    starts_on: date | None = None
    ends_on: date | None = None
    topic_ids: list[UUID] = Field(default_factory=list, max_length=50)
    source: str = Field(default="entered in app", max_length=200)

    @model_validator(mode="after")
    def _dates(self) -> TeachingEntryIn:
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("ends_on is before starts_on")
        return self


class TeachingEntryOut(BaseModel):
    id: UUID
    subject_id: UUID
    term: str
    label: str
    starts_on: date | None
    ends_on: date | None
    topic_ids: list[UUID]
    source: str


class UpcomingIn(_In):
    subject_id: UUID
    title: str = Field(max_length=200)
    due_at: datetime
    objective_ids: list[UUID] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)


class UpcomingOut(BaseModel):
    id: UUID
    subject_id: UUID
    title: str
    due_at: datetime
    objective_ids: list[UUID]
    notes: str | None


class SchoolResultIn(_In):
    subject_id: UUID
    title: str = Field(max_length=200)
    assessed_on: date
    score: Decimal = Field(ge=0)
    max_score: Decimal = Field(gt=0)
    objective_ids: list[UUID] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _score(self) -> SchoolResultIn:
        if self.score > self.max_score:
            raise ValueError("score exceeds max_score")
        return self


class SchoolResultOut(SchoolResultIn):
    id: UUID
