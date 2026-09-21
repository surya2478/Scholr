from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ClassifierCategory = Literal[
    "self_harm",
    "abuse_exploitation",
    "sexual_content",
    "violence",
    "bullying",
    "personal_info",
    "dangerous_activity",
    "hate",
    "academic_integrity",
    "distress",
    "none",
]


class ClassifierOutput(BaseModel):
    category: ClassifierCategory
    severity: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(default="", max_length=400)


class CrisisResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    contact: str
    region: str
    hours: str | None = None


class CrisisResources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool = False
    entries: list[CrisisResource] = Field(default_factory=list)


class SafetyPolicyFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    reviewed_by_parent: bool = False
    crisis_resources: CrisisResources
    responses: dict[str, str]


class IncidentOut(BaseModel):
    id: UUID
    student_id: UUID
    occurred_at: datetime
    category: str
    severity: int
    action_taken: str
    rule_ids: list[str]
    policy_version: str
    escalation_status: str
    notified_at: datetime | None
    resolved_at: datetime | None
    notes: str | None


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    escalation_status: Literal["acknowledged", "resolved"]
    notes: str | None = Field(default=None, max_length=2000)
