from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MasteryOut(BaseModel):
    objective_id: UUID
    objective_code: str
    objective_statement: str
    subject_id: UUID
    level: int
    level_name: str
    score: float
    mastery_confidence: float
    evidence_count: int
    independent_successes: int
    distinct_days: int
    last_demonstrated_at: datetime | None
    retention_risk: str
    rule_version: str


class SkillOut(BaseModel):
    subject_id: UUID
    skill_code: str
    skill_name: str
    score: float
    evidence_count: int
    rule_version: str


class EvidenceOut(BaseModel):
    event_id: UUID
    evaluation_id: UUID
    attempt_id: UUID
    occurred_at: datetime
    score: float
    help_level: int
    evaluation_confidence: float
    exam_style: bool
    stretch: bool
    retention_check: bool
    overridden: bool
