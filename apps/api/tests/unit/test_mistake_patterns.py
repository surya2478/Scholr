"""Mistake bank status rules (ARCHITECTURE §14) as a pure projection of events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.events.service import EventView
from app.modules.mistakes.service import derive_patterns

T0 = datetime(2026, 10, 1, 16, 0, tzinfo=UTC)
STUDENT, SUBJECT, OBJ = uuid4(), uuid4(), uuid4()


def ev(event_type: str, payload: dict[str, object], *, hours: float) -> EventView:
    return EventView(
        id=uuid4(),
        student_id=STUDENT,
        type=event_type,
        occurred_at=T0 + timedelta(hours=hours),
        subject_id=SUBJECT,
        objective_ids=(OBJ,),
        payload=payload,
    )


def evaluated(
    evaluation_id: UUID, *, hours: float, status: str = "final", retention: bool = False, help_level: int = 0
) -> EventView:
    return ev(
        "attempt_evaluated",
        {
            "attempt_id": str(uuid4()),
            "evaluation_id": str(evaluation_id),
            "marks_awarded": 2,
            "marks_available": 2,
            "help_level": help_level,
            "evaluation_confidence": 0.9,
            "status": status,
            "retention_check": retention,
        },
        hours=hours,
    )


def diagnosed(evaluation_id: UUID, *, hours: float, severity: str = "medium") -> EventView:
    return ev(
        "mistake_diagnosed",
        {
            "evaluation_id": str(evaluation_id),
            "attempt_id": str(uuid4()),
            "mistake_type": "calculation",
            "severity": severity,
            "fingerprint": "calculation:premature_rounding",
        },
        hours=hours,
    )


def only_state(history: list[EventView]):  # noqa: ANN201
    [state] = derive_patterns(history).values()
    return state


def with_mistake(hours: float) -> list[EventView]:
    e = uuid4()
    return [evaluated(e, hours=hours), diagnosed(e, hours=hours)]


def test_diagnosis_opens_pattern_and_its_own_evaluation_is_not_clean() -> None:
    state = only_state(with_mistake(0))
    assert (state.status, len(state.occurrences), state.clean_streak) == ("open", 1, 0)


def test_two_clean_attempts_make_it_improving_and_review_evaluations_do_not_count() -> None:
    history = [*with_mistake(0), evaluated(uuid4(), hours=1, status="needs_review"), evaluated(uuid4(), hours=2)]
    assert only_state(history).status == "open"
    assert only_state([*history, evaluated(uuid4(), hours=3)]).status == "improving"


def test_resolution_needs_two_days_and_a_retention_item() -> None:
    same_day = [*with_mistake(0), evaluated(uuid4(), hours=1), evaluated(uuid4(), hours=2, retention=True)]
    assert only_state(same_day).status == "improving"
    two_days = [*with_mistake(0), evaluated(uuid4(), hours=1), evaluated(uuid4(), hours=30, retention=True)]
    assert only_state(two_days).status == "resolved"


def test_recurrence_reopens_and_counts() -> None:
    history = [*with_mistake(0), evaluated(uuid4(), hours=1), evaluated(uuid4(), hours=30, retention=True)]
    state = only_state([*history, *with_mistake(60)])
    assert (state.status, len(state.occurrences), state.clean_streak) == ("open", 2, 0)


DAY = 24


def test_an_answer_she_was_helped_through_is_not_a_repair() -> None:
    """Improvement 8: only an unaided answer counts towards fixing a mistake (PRINCIPLES 18-20)."""
    helped = [
        *with_mistake(0),
        evaluated(uuid4(), hours=DAY, help_level=2),
        evaluated(uuid4(), hours=5 * DAY, help_level=3),
    ]
    state = only_state(helped)
    assert (state.status, state.repair_days, state.clean_streak) == ("open", [], 0)


def test_two_unaided_repairs_three_days_apart_close_it_without_a_study_test() -> None:
    """Before 14 Nov 2026 a mistake could only close through a parent-set retention test."""
    first = [*with_mistake(0), evaluated(uuid4(), hours=DAY)]
    state = only_state(first)
    assert state.status == "open" and state.due_on == (T0 + timedelta(hours=DAY)).date() + timedelta(days=3)
    too_soon = only_state([*first, evaluated(uuid4(), hours=2 * DAY)])
    assert too_soon.status == "improving" and too_soon.resolved_on is None  # two in a row, but not yet spaced
    closed = only_state([*first, evaluated(uuid4(), hours=4 * DAY)])
    assert (closed.status, closed.due_on) == ("resolved", None)
    assert closed.resolved_on == (T0 + timedelta(hours=4 * DAY)).date()


def test_a_mistake_is_due_the_day_after_it_and_again_after_a_recurrence() -> None:
    state = only_state(with_mistake(0))
    assert state.due_on == T0.date() + timedelta(days=1)
    back = only_state([*with_mistake(0), evaluated(uuid4(), hours=DAY), *with_mistake(10 * DAY)])
    assert (back.status, back.repair_days) == ("open", [])
    assert back.due_on == (T0 + timedelta(hours=10 * DAY)).date() + timedelta(days=1)
