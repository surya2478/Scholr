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


AssessmentKind = Literal["practice", "quiz", "baseline", "post", "retention", "exam_style", "topic_exam"]


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
    config: dict | None = None


class AssessmentBriefOut(BaseModel):
    id: UUID
    subject_id: UUID
    kind: str
    form_code: str | None
    status: str
    total_marks: int
    created_at: datetime
    submitted_at: datetime | None
    config: dict | None = None


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


class QuestionsByObjectivesIn(BaseModel):
    subject_id: UUID
    objective_ids: list[UUID] = Field(min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)


class ExamFromTopicsIn(BaseModel):
    subject_id: UUID
    title: str = Field(min_length=3, max_length=120)
    exam_category: Literal["practice_exam", "pre_term", "term", "mid_term", "final"]
    objective_ids: list[UUID] = Field(min_length=1, max_length=50)
    target_marks: int = Field(default=40, ge=5, le=120)
    duration_minutes: int = Field(default=60, ge=15, le=240)


BookmarkTag = Literal["examiner_trap", "calc_heavy", "must_revise"]


class BookmarkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: BookmarkTag = "must_revise"
    note: str | None = Field(default=None, max_length=500)


class BookmarkOut(BaseModel):
    question_item_id: UUID
    subject_id: UUID
    source_ref: str | None
    stem: str
    marks: int
    tag: BookmarkTag
    note: str | None
    saved_at: datetime


class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    icon: str = Field(default="📓", max_length=16)
    color: str = Field(default="amber", max_length=32)
    subject_id: UUID | None = None


class NotebookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=32)


class NotebookItemCreate(BaseModel):
    question_item_id: UUID
    student_notes: str | None = None


class NotebookItemOut(BaseModel):
    id: UUID
    notebook_id: UUID
    question_item_id: UUID
    student_notes: str | None
    created_at: datetime
    question: QuestionOut | None = None


class NotebookOut(BaseModel):
    id: UUID
    student_id: UUID
    title: str
    description: str | None
    icon: str
    color: str
    subject_id: UUID | None
    item_count: int
    created_at: datetime
    updated_at: datetime


class ExamFromNotebookIn(BaseModel):
    notebook_id: UUID
    title: str = Field(min_length=3, max_length=120)
    duration_minutes: int = Field(default=45, ge=10, le=180)


class ExamFromMistakesIn(BaseModel):
    subject_id: UUID
    title: str = Field(default="Mistake Killer Drill", min_length=3, max_length=120)
    duration_minutes: int = Field(default=30, ge=10, le=120)
    limit: int = Field(default=5, ge=1, le=15)


class TimeSinkItem(BaseModel):
    position: int
    question_id: str
    stem_snippet: str
    marks_available: float
    marks_awarded: float
    time_spent_s: int
    pace_seconds_per_mark: float


class TopicBreakdownItem(BaseModel):
    topic_id: str
    code: str
    title: str
    marks_available: float
    marks_awarded: float
    accuracy_pct: float
    status: Literal["mastered", "solid", "needs_work"]


class DifficultyBreakdownItem(BaseModel):
    tier: int
    label: str
    marks_available: float
    marks_awarded: float
    accuracy_pct: float


class PacingSummary(BaseModel):
    total_time_seconds: int
    avg_time_per_question_s: float
    avg_time_per_mark_s: float
    target_pace_s_per_mark: float
    pace_status: Literal["optimal", "rushed", "slow"]


class AssessmentReportOut(BaseModel):
    assessment_id: UUID
    title: str
    kind: str
    total_questions: int
    total_marks_available: float
    total_marks_awarded: float
    score_percentage: float
    projected_grade: str
    pacing: PacingSummary
    time_sinks: list[TimeSinkItem]
    topic_breakdown: list[TopicBreakdownItem]
    difficulty_breakdown: list[DifficultyBreakdownItem]
    mistake_types_summary: dict[str, int]
    action_plan: list[str]
