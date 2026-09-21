"""Guardian trends and suggestions: how answers were reached, week boundaries, and the plain-language next steps."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.modules.progress.schemas import FocusOut, UpcomingBriefOut, WinOut
from app.modules.progress.service import help_mix, suggestions, week_start_dates
from tests.unit.test_monthly_summary import ev

SUBJECT = uuid4()


def evaluated(help_level: int) -> Any:
    payload = {
        "attempt_id": str(uuid4()),
        "marks_awarded": 1,
        "marks_available": 2,
        "status": "final",
        "help_level": help_level,
    }
    return ev("attempt_evaluated", payload)


def test_help_mix_splits_answers_by_how_they_were_reached() -> None:
    window = [evaluated(0), evaluated(1), evaluated(2), evaluated(4), evaluated(5), ev("help_given", {"level": 3})]
    assert help_mix(window) == (2, 2, 1)  # a nudge still counts as without help; a full solution is its own band


def test_week_start_dates_are_mondays_oldest_first() -> None:
    starts = week_start_dates(date(2026, 9, 16), 3)  # a Wednesday
    assert starts == [date(2026, 8, 31), date(2026, 9, 7), date(2026, 9, 14)]


def win(statement: str) -> WinOut:
    return WinOut(
        subject_id=SUBJECT,
        objective_id=uuid4(),
        objective_code="E2.5",
        objective_statement=statement,
        level_name="Competent",
        last_demonstrated_at=datetime(2026, 9, 15, tzinfo=UTC),
    )


def upcoming(due_at: datetime, *, secure: int | None = 4, total: int = 5) -> UpcomingBriefOut:
    return UpcomingBriefOut(
        subject_id=SUBJECT,
        subject_name="Mathematics",
        title="Maths assessment",
        due_at=due_at,
        objectives_total=total,
        objectives_secure=secure,
        notes=None,
    )


def test_suggestions_cover_a_win_a_recurring_mistake_and_the_next_assessment() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    focus = [
        FocusOut(
            kind="mistake",
            subject_id=SUBJECT,
            objective_id=uuid4(),
            objective_code="E2.5",
            label="Sign errors when expanding brackets",
        )
    ]
    out = suggestions(
        wins=[win("Solve quadratic equations")],
        focus=focus,
        upcoming=[upcoming(now + timedelta(days=2))],
        timezone="Asia/Dubai",
        now=now,
    )
    leads = [s.lead for s in out]
    assert leads[0] == "Celebrate" and leads[1] == "Talk it through"
    assert leads[2].startswith("Before Friday")
    assert "4 of 5 topics are secure" in out[2].text
    assert "sign errors" in out[1].text


def test_a_distant_assessment_is_not_suggested_and_a_quiet_month_still_says_something() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    out = suggestions(wins=[], focus=[], upcoming=[upcoming(now + timedelta(days=13))], timezone="Asia/Dubai", now=now)
    assert [s.lead for s in out] == ["This week"]
