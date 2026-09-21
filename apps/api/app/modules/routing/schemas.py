from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RouteSource = Literal["assessment_lock", "session", "rules", "classifier", "ask"]
Intent = Literal[
    "explain", "practice", "help_on_attempt", "check_answer", "plan", "progress", "off_topic", "wellbeing", "assessment"
]


class RouteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    subject_id: UUID | None = None  # context from the UI (current page or session)
    objective_id: UUID | None = None


class RouteChoice(BaseModel):
    subject_id: UUID
    subject_name: str
    objective_id: UUID | None
    objective_code: str | None
    label: str


class RouteOut(BaseModel):
    source: RouteSource
    intent: Intent
    subject_id: UUID | None
    subject_name: str | None
    objective_id: UUID | None
    objective_code: str | None
    confidence: float
    choices: list[RouteChoice] = Field(default_factory=list)
    assessment_id: UUID | None = None


class ClassifierOut(BaseModel):
    """LLM output for route_classify."""

    intent: Literal[
        "explain", "practice", "help_on_attempt", "check_answer", "plan", "progress", "off_topic", "wellbeing"
    ]
    subject_code: str | None = None
    objective_code: str | None = None
    confidence: float = Field(ge=0, le=1)
