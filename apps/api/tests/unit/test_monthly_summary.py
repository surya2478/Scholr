"""Guardian monthly summary: month arithmetic in the student's timezone and aggregation of marked work."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.errors import ApiError
from app.modules.events.service import EventView
from app.modules.progress.service import (
    marked_answers,
    month_start,
    month_subject,
    month_totals,
    month_window,
    shift_month,
)

SUBJECT = uuid4()
AT = datetime(2026, 9, 10, 8, tzinfo=UTC)


def ev(kind: str, payload: dict[str, Any], *, at: datetime = AT, subject: UUID | None = SUBJECT) -> EventView:
    return EventView(
        id=uuid4(), student_id=uuid4(), type=kind, occurred_at=at, subject_id=subject, objective_ids=(), payload=payload
    )


def evaluated(
    attempt: UUID, awarded: float, available: float, *, status: str = "final", help_level: int = 0
) -> EventView:
    payload = {
        "attempt_id": str(attempt),
        "marks_awarded": awarded,
        "marks_available": available,
        "status": status,
        "help_level": help_level,
    }
    return ev("attempt_evaluated", payload)


def test_month_arithmetic_and_months_not_started() -> None:
    assert shift_month(date(2026, 12, 1), 1) == date(2027, 1, 1)
    assert shift_month(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert month_start(None, today=date(2026, 9, 15)) == date(2026, 9, 1)
    assert month_start("2026-08", today=date(2026, 9, 15)) == date(2026, 8, 1)
    with pytest.raises(ApiError):
        month_start("2026-10", today=date(2026, 9, 15))


def test_month_window_uses_the_student_timezone() -> None:
    start, end = month_window(date(2026, 9, 1), "Asia/Dubai")
    assert (start, end) == (datetime(2026, 8, 31, 20, tzinfo=UTC), datetime(2026, 9, 30, 20, tzinfo=UTC))


def test_reviews_settle_marks_and_help_counts_against_independence() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    window = [
        evaluated(a, 2, 3),
        evaluated(b, 0, 4, status="needs_review", help_level=3),
        ev("evaluation_overridden", {"attempt_id": str(b), "marks_awarded": 3, "marks_available": 4}),
        evaluated(c, 1, 2, status="needs_review"),
        ev("session_ended", {"session_id": str(uuid4()), "active_minutes": 25}),
        ev("mistake_diagnosed", {"attempt_id": str(a), "fingerprint": "calculation:sign_error"}),
        ev("plan_item_completed", {"plan_item_id": str(uuid4())}, subject=None),
    ]
    answers = marked_answers(window)
    assert answers[str(b)].settled and answers[str(b)].awarded == 3

    subject = month_subject(window, subject_id=SUBJECT, subject_name="Maths", topics_secured=None)
    assert (subject.answers_marked, subject.awaiting_review) == (3, 1)
    assert (subject.marks_awarded, subject.marks_available, subject.accuracy) == (5, 7, round(5 / 7, 3))
    assert subject.independent_share == round(2 / 3, 3)
    assert (subject.sessions, subject.study_minutes, subject.mistakes_found) == (1, 25, 1)

    totals = month_totals(window, timezone="Asia/Dubai")
    assert (totals.answers_marked, totals.active_days, totals.study_minutes) == (3, 1, 25)


def test_empty_month_has_no_accuracy() -> None:
    totals = month_totals([], timezone="Asia/Dubai")
    assert (totals.answers_marked, totals.accuracy, totals.active_days) == (0, None, 0)
