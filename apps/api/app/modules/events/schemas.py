"""Payload schemas per learning event type (schema_version 1).

Payloads carry ids, numbers and flags only — never conversation text or answers (those live in their own
tables). ``extra="forbid"`` makes that a hard rule rather than a convention.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Marks(_Payload):
    marks_awarded: float = Field(ge=0)
    marks_available: float = Field(gt=0)

    @model_validator(mode="after")
    def _awarded_within_available(self) -> _Marks:
        if self.marks_awarded > self.marks_available:
            raise ValueError("marks_awarded exceeds marks_available")
        return self


class SessionStarted(_Payload):
    session_id: UUID
    mode: Literal["learn", "practice", "test"]


class SessionEnded(_Payload):
    session_id: UUID
    active_minutes: int = Field(ge=0)


class ExplanationViewed(_Payload):
    session_id: UUID | None = None
    lesson_id: UUID | None = None  # read on a topic page (docs/STUDENT-APP.md AC-U7)


class AttemptSubmitted(_Payload):
    attempt_id: UUID
    question_item_id: UUID
    assessment_id: UUID | None = None
    session_id: UUID | None = None


class AttemptEvaluated(_Marks):
    attempt_id: UUID
    evaluation_id: UUID
    help_level: int = Field(ge=0, le=5)
    evaluation_confidence: float = Field(ge=0, le=1)
    status: Literal["final", "needs_review"]
    exam_style: bool = False
    stretch: bool = False
    retention_check: bool = False
    # Marks per skill code (e.g. {"AO1": 2, "AO2": 1.5}) when the pipeline splits marks by assessment objective.
    skill_marks: dict[str, float] | None = None


class EvaluationOverridden(_Marks):
    attempt_id: UUID
    evaluation_id: UUID
    reviewer_user_id: UUID


class HelpRequested(_Payload):
    session_id: UUID | None = None
    attempt_id: UUID | None = None


class HelpGiven(_Payload):
    level: int = Field(ge=0, le=5)
    session_id: UUID | None = None
    attempt_id: UUID | None = None


class SelfExplanationGiven(_Payload):
    attempt_id: UUID | None = None
    message_id: UUID | None = None


class ConfidenceReported(_Payload):
    confidence: int = Field(ge=1, le=4)
    attempt_id: UUID | None = None


class MistakeDiagnosed(_Payload):
    evaluation_id: UUID
    attempt_id: UUID
    mistake_type: str = Field(max_length=32)
    severity: Literal["low", "medium", "high"]
    fingerprint: str = Field(max_length=120)


class MistakeResolved(_Payload):
    pattern_id: UUID


class SchoolResultRecorded(_Payload):
    school_result_id: UUID
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)


class ExternalTrainingLogged(_Payload):
    """A session of the external IIT Foundation programme (Phase 3). Counts only — no weakness wording."""

    external_training_log_id: UUID
    kind: Literal["class", "test", "homework", "practice"]
    duration_min: int | None = Field(default=None, ge=0, le=720)
    score: float | None = Field(default=None, ge=0)
    max_score: float | None = Field(default=None, gt=0)
    questions_attempted: int | None = Field(default=None, ge=0)
    questions_missed: int | None = Field(default=None, ge=0)
    lessons: int = Field(ge=0)
    weak_lessons: int = Field(ge=0)


class PlanItemCompleted(_Payload):
    plan_item_id: UUID


class PlanItemSkipped(_Payload):
    plan_item_id: UUID


PAYLOAD_SCHEMAS: dict[str, type[_Payload]] = {
    "session_started": SessionStarted,
    "session_ended": SessionEnded,
    "explanation_viewed": ExplanationViewed,
    "attempt_submitted": AttemptSubmitted,
    "attempt_evaluated": AttemptEvaluated,
    "evaluation_overridden": EvaluationOverridden,
    "help_requested": HelpRequested,
    "help_given": HelpGiven,
    "self_explanation_given": SelfExplanationGiven,
    "confidence_reported": ConfidenceReported,
    "mistake_diagnosed": MistakeDiagnosed,
    "mistake_resolved": MistakeResolved,
    "school_result_recorded": SchoolResultRecorded,
    "external_training_logged": ExternalTrainingLogged,
    "plan_item_completed": PlanItemCompleted,
    "plan_item_skipped": PlanItemSkipped,
}

# Events that projections attribute to objectives, so they must name at least one.
REQUIRES_OBJECTIVES = frozenset(
    {"attempt_evaluated", "evaluation_overridden", "explanation_viewed", "mistake_diagnosed"}
)
