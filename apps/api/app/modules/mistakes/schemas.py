from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class MistakeOut(BaseModel):
    id: UUID
    subject_id: UUID
    objective_id: UUID | None
    objective_code: str | None
    mistake_type: str
    fingerprint: str
    description: str
    severity: str
    occurrences: int
    status: str
    first_seen: datetime
    last_seen: datetime
    resolution: str | None = None
    due_on: date | None = None  # when to try it again; None once resolved
    resolved_on: date | None = None
