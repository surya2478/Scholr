from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9._:-]{8,64}$"


class QuestionOut(BaseModel):
    """What a student sees before answering: no answer, no mark scheme."""

    id: UUID
    subject_id: UUID
    source_ref: str | None
    context: str | None
    stem: str
    marks: int
    command_word: str | None
    has_diagram: bool
    calculator_allowed: bool | None
    objective_ids: list[UUID]


class AttemptMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_item_id: UUID
    idempotency_key: str = Field(pattern=IDEMPOTENCY_PATTERN)
    pre_confidence: int | None = Field(default=None, ge=1, le=4)
    assessment_id: UUID | None = None
    session_id: UUID | None = None
    time_spent_s: int | None = Field(default=None, ge=0, le=36000)


class AttemptCreate(AttemptMeta):
    working: str | None = Field(default=None, max_length=10000)
    final_answer: str | None = Field(default=None, max_length=500)


class TranscriptionConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    working: str = Field(max_length=10000)
    final_answer: str | None = Field(default=None, max_length=500)


class TranscriptionOut(BaseModel):
    working: str | None
    final_answer: str | None
    legibility: str | None
    uncertain: list[str]
    confirmed_at: datetime | None
    edited: bool


AssessmentKind = Literal["practice", "quiz", "baseline", "post", "retention", "exam_style"]


class AssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: UUID
    kind: AssessmentKind
    form_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,32}$")
    question_item_ids: list[UUID] = Field(min_length=1, max_length=40)

    @field_validator("question_item_ids")
    @classmethod
    def _unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("question_item_ids must not repeat")
        return value


class ScoreOut(BaseModel):
    awarded: float
    available: int
    answered: int
    unmarked: int  # answered but not evaluated yet
    pending_review: int  # evaluated but provisional (needs_review)
    final: bool  # submitted, every answer marked, nothing waiting for review


class AssessmentItemOut(BaseModel):
    position: int
    question_item_id: UUID
    marks: int
    question: QuestionOut | None  # hidden from the student until the test is started
    attempt_id: UUID | None
    evaluation_id: UUID | None
    evaluation_status: str | None
    marks_awarded: float | None


class AssessmentOut(BaseModel):
    id: UUID
    student_id: UUID
    subject_id: UUID
    kind: str
    form_code: str | None
    status: str
    no_help: bool
    total_marks: int
    created_at: datetime
    started_at: datetime | None
    submitted_at: datetime | None
    items: list[AssessmentItemOut]
    score: ScoreOut | None  # hidden from the student during a study test


class AssessmentBriefOut(BaseModel):
    id: UUID
    subject_id: UUID
    kind: str
    form_code: str | None
    status: str
    total_marks: int
    created_at: datetime
    submitted_at: datetime | None


AttemptStatus = Literal["awaiting_transcription", "awaiting_confirmation", "ready", "evaluated"]


class AttemptOut(BaseModel):
    id: UUID
    question_item_id: UUID
    status: AttemptStatus
    working: str | None
    final_answer: str | None
    photo_count: int
    transcription: TranscriptionOut | None
    pre_confidence: int | None
    max_assistance_level: int
    submitted_at: datetime
    evaluation_id: UUID | None


class ExaminerInsightOut(BaseModel):
    """A point from a Principal Examiner Report, paraphrased — always shown with where it came from (AC-R6)."""

    kind: Literal["common_error", "what_scored", "advice"]
    text: str
    question_ref: str | None  # null = about the whole paper
    component: str
    exam_series: str
    attribution: str  # "Principal Examiner Report for Teachers, May/June 2025 — Paper 11, Question 1(a)(ii)"


class ExaminerInsightsOut(BaseModel):
    """Shown only once an answer to this question has been marked: the reports name the answers that scored."""

    item_ref: str | None
    question: list[ExaminerInsightOut] = Field(default_factory=list)
    paper: list[ExaminerInsightOut] = Field(default_factory=list)
    note: str = (
        "Paraphrased from Cambridge's report on how candidates answered this paper. It is the examiner's "
        "comment on that year's candidates, not Scholr's advice."
    )
