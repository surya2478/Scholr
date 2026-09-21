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


def evaluated(evaluation_id: UUID, *, hours: float, status: str = "final", retention: bool = False) -> EventView:
    return ev(
        "attempt_evaluated",
        {
            "attempt_id": str(uuid4()),
            "evaluation_id": str(evaluation_id),
            "marks_awarded": 2,
            "marks_available": 2,
            "help_level": 0,
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
