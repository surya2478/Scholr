from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class PatternOut(BaseModel):
    kind: str
    severity: Literal["notice", "watch"]
    title: str
    # What was observed, with its numbers. Never a diagnosis of the student (AC-C2).
    observation: str
    why: str
    window_days: int
    rule_version: str
    facts: dict[str, str]


class CriticOut(BaseModel):
    window_days: int
    from_day: date
    to_day: date
    rule_version: str
    template_version: str
    patterns: list[PatternOut]
    # Set when nothing fired: an empty panel would read as "not working" rather than "nothing to say".
    nothing_stands_out: str | None
    active_days: int
    study_minutes: int
    answers: int
