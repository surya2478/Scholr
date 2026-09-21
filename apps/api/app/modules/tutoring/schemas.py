from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assessment.schemas import QuestionOut


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: UUID
    objective_id: UUID | None = None
    mode: Literal["learn", "practice", "test"] = "practice"
    # Drill one command word. The readiness view lists them weakest first (AC-R4).
    command_word: str | None = Field(default=None, max_length=32)


class SessionStateOut(BaseModel):
    phase: str
    item_id: UUID | None
    help_level: int
    needs_similar_question: bool


class SessionOut(BaseModel):
    id: UUID
    subject_id: UUID
    objective_id: UUID | None
    mode: str
    command_word: str | None = None
    started_at: datetime
    ended_at: datetime | None
    active_minutes: int
    state: SessionStateOut


class CitationOut(BaseModel):
    source_title: str
    printed_page: int | None
    heading_path: str | None


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    assistance_level: int
    retrieval_state: str | None
    citations: list[CitationOut]
    safety_status: str
    created_at: datetime


ReplyKind = Literal["help", "ask_for_attempt", "explanation", "safety", "notice"]


class TurnOut(BaseModel):
    session: SessionOut
    kind: ReplyKind
    reply: MessageOut
    check_question: str | None = None


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


class HelpIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str | None = Field(default=None, max_length=2000)


class NextItemOut(BaseModel):
    session: SessionOut
    question: QuestionOut | None
    notice: str | None = None


class TutorReply(BaseModel):
    """LLM output for tutor_help / tutor_explain."""

    message: str = Field(max_length=2500)
    check_question: str | None = Field(default=None, max_length=400)
    citations: list[int] = Field(default_factory=list, max_length=10)
    uses_general_knowledge: bool = False


class EssayPlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: UUID
    question_item_id: UUID
    message: str = Field(default="", max_length=1000)


class EssayPlanOut(BaseModel):
    """A plan, never prose. Anything she could hand in has been stripped before this is built (AC-R5)."""

    question_item_id: UUID
    command_word: str | None
    marks: int
    for_points: list[str]
    against_points: list[str]
    evidence: list[str]
    conclusion_direction: str
    watch_out: list[str]
    # Set when she asked for the answer itself. Scholr's wording, not the model's.
    refusal: str
    # How many proposed lines read as prose and were removed. Shown so the guard is visible, not silent.
    removed_as_prose: int
    citations: list[CitationOut]
    rule_version: str


class SpeechIn(BaseModel):
    """A spoken question, recorded in the browser as a WAV and sent base64-encoded (docs/STUDENT-APP.md §16)."""

    model_config = ConfigDict(extra="forbid")
    audio: str = Field(min_length=1, max_length=5_400_000)  # base64 of at most ~4 MB
    format: Literal["wav"] = "wav"


class SpeechOut(BaseModel):
    text: str  # for her to read and edit; nothing is sent to the Tutor until she presses Send
    unclear: bool  # some words were a best guess
