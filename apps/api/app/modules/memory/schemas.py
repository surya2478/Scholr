from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MemoryKind = Literal["strength", "difficulty", "misconception", "preference", "note"]


class ProposedStatement(BaseModel):
    """One statement proposed by the summarizer. Cites digest references such as "E2"."""

    kind: MemoryKind
    statement: str = Field(min_length=3, max_length=400)
    evidence: list[str] = Field(default_factory=list, max_length=10)


class SummaryOutput(BaseModel):
    statements: list[ProposedStatement] = Field(default_factory=list, max_length=8)


class MemoryOut(BaseModel):
    id: UUID
    subject_id: UUID | None
    kind: str
    statement: str
    evidence_count: int
    status: str
    created_at: datetime
    updated_at: datetime
