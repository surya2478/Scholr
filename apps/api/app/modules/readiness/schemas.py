from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Band = Literal["secure", "developing", "weak", "unknown"]


class SkillReadinessOut(BaseModel):
    skill_code: str
    skill_name: str
    share: float | None
    weighting: float | None
    band: Band
    answers_with_split: int
    answers_seen: int
    marks_available: float
    marks_awarded: float


class TopicReadinessOut(BaseModel):
    topic_id: UUID
    topic_code: str
    topic_name: str
    share: float | None
    band: Band
    answers: int
    objectives_total: int
    objectives_secure: int


class CommandWordOut(BaseModel):
    """How she does on one command word — the drill list is built from the weakest of these (AC-R4)."""

    command_word: str
    share: float | None
    answers: int
    marks_available: float
    items_available: int


class ReadinessOut(BaseModel):
    subject_id: UUID
    subject_name: str
    exam_session: str | None
    days_to_exam: int | None
    rule_version: str
    # Her share of marks weighted the way the exam weights each AO, over the objectives with enough evidence.
    weighted_share: float | None
    # What we could not judge, said plainly rather than shown as zero.
    notes: list[str]
    skills: list[SkillReadinessOut]
    topics: list[TopicReadinessOut]
    command_words: list[CommandWordOut]
    papers_available: int
    papers_sat: int
    next_step: str | None = None


class PastPaperOut(BaseModel):
    """A whole past paper that can be sat under its real time limit (AC-R3)."""

    paper_ref: str  # e.g. "0495/11/MJ25"
    component_code: str | None
    label: str
    # What the bank holds for this paper: every question, including the ones a candidate would not answer.
    questions: int
    bank_marks: int
    # What a candidate actually sits, from the syllabus component (Sociology: 80 marks, two questions of
    # three, because both papers offer a choice).
    paper_marks: int | None
    duration_min: int | None
    sat_on: date | None
    assessment_id: UUID | None
    # The paper's question numbers, and which of them she chooses between (subject config `paper_structure`).
    # Empty choose_from: every question is compulsory.
    question_numbers: list[str] = Field(default_factory=list)
    compulsory: list[str] = Field(default_factory=list)
    choose_from: list[str] = Field(default_factory=list)
    choose_count: int = 0
    # The sitting is started and not yet submitted: open it again rather than starting afresh.
    in_progress: bool = False


class SittingIn(BaseModel):
    """Start a timed sitting of one past paper."""

    model_config = ConfigDict(extra="forbid")

    paper_ref: str = Field(min_length=3, max_length=64)
    # The optional questions she is answering. Both Sociology papers offer a choice.
    questions: list[str] = Field(default_factory=list, max_length=6)


class SittingOut(BaseModel):
    assessment_id: UUID
    paper_ref: str
    label: str
    questions: list[str]
    items: int
    marks: int
    duration_min: int | None
    minutes_left: int | None
    over_time: bool
    status: str


class TimedItemOut(BaseModel):
    question_item_id: UUID
    label: str
    marks: int
    command_word: str | None
    objective_code: str | None
    objective_statement: str | None
    minutes: int  # her papers' own pace: their minutes over their marks, times this question's marks


class TimedQuestionOut(BaseModel):
    """This week's timed long answer in one subject (readiness/timed.py)."""

    subject_id: UUID
    subject_name: str
    week_start: date
    item: TimedItemOut
    assessment_id: UUID | None  # set once she has started it
    status: Literal["to_do", "in_progress", "submitted", "marked"]
    minutes_used: int | None = None
    over_time: bool = False
