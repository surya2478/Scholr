"""Planner v1 rules (ARCHITECTURE §16): capacity, priority, fill order, caps, overload, AC-P1, AC-P2."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.modules.planner.engine import (
    CommitmentIn,
    ObjectiveSignal,
    build_plan,
    day_capacity,
    entry_for,
    priority,
)
from app.tools.dates import RecurrenceError, occurs_on, parse_rrule

MONDAY = date(2026, 10, 5)
SUBJECT = uuid4()
AVAILABILITY = {0: 120, 1: 120, 2: 120, 3: 120, 4: 90, 5: 150, 6: 60}


def signal(**kw: object) -> ObjectiveSignal:
    return ObjectiveSignal(objective_id=uuid4(), subject_id=SUBJECT, **kw)  # type: ignore[arg-type]


def test_recurrence_rules() -> None:
    assert parse_rrule("FREQ=WEEKLY;BYDAY=MO,WE,FR") == frozenset({0, 2, 4})
    assert occurs_on("FREQ=DAILY", MONDAY)
    assert not occurs_on("FREQ=WEEKLY;BYDAY=TU", MONDAY)
    for bad in ("FREQ=MONTHLY", "FREQ=WEEKLY", "FREQ=WEEKLY;BYDAY=XX", "FREQ=WEEKLY;BYDAY=MO;INTERVAL=2", "BYDAY"):
        with pytest.raises(RecurrenceError):
            parse_rrule(bad)


def test_capacity_subtracts_commitments_buffer_and_lightens_one_day() -> None:
    iit = [CommitmentIn("IIT class", "FREQ=WEEKLY;BYDAY=TU", 60)]
    tuesday = day_capacity(date(2026, 10, 6), AVAILABILITY, iit)
    assert (tuesday.available, tuesday.commitments, tuesday.buffer, tuesday.minutes) == (120, 60, 9, 51)
    sunday = day_capacity(date(2026, 10, 11), AVAILABILITY, [])
    assert sunday.lighter_day and sunday.minutes == int((60 - 9) * 0.6)
    broken = day_capacity(MONDAY, AVAILABILITY, [CommitmentIn("odd", "FREQ=YEARLY", 30)])
    assert broken.unsupported_rules == ("odd",) and broken.commitments == 0


def test_priority_formula_and_kinds() -> None:
    assert priority(signal(assessment_due=True, retention_risk="high", mastery_level=3)) == 5
    assert priority(signal(mistake_severity="high", school_topic=True, mastery_level=2)) == 5
    assert priority(signal(mastery_level=4)) == 0.5
    assert entry_for(signal(assessment_due=True)).kind == "assessment"  # type: ignore[union-attr]
    assert entry_for(signal(mistake_severity="medium", mastery_level=3)).kind == "mistake_fix"  # type: ignore[union-attr]
    assert entry_for(signal(retention_risk="high", mastery_level=4)).kind == "revision"  # type: ignore[union-attr]
    assert entry_for(signal(mastery_level=3)) is None  # nothing to do


def test_fill_never_exceeds_capacity_and_puts_core_first() -> None:  # AC-P1
    signals = [signal(mastery_level=1), signal(mastery_level=4), signal(retention_risk="high", mastery_level=3)]
    draft = build_plan(signals, capacity_minutes=40, control_objectives=set())
    assert sum(e.est_minutes for e in draft.entries) <= 40
    assert draft.entries[0].kind == "revision"
    assert [e.kind for e in draft.entries] == ["revision", "practice"]
    assert [e.kind for e in draft.dropped] == ["challenge"]


def test_new_learning_is_capped_at_forty_percent() -> None:
    signals = [signal(school_topic=True) for _ in range(3)]  # no evidence yet: new learning, 25 minutes each
    draft = build_plan(signals, capacity_minutes=100, control_objectives=set())
    assert [e.kind for e in draft.entries] == ["school_topic"]  # 25 <= 40, a second would make 50 > 40
    assert len(draft.dropped) == 2


def test_overload_drops_optional_items_and_says_so() -> None:
    core = [signal(assessment_due=True, mastery_level=2) for _ in range(3)]  # 90 minutes of core
    draft = build_plan([*core, signal(mastery_level=1)], capacity_minutes=60, control_objectives=set())
    assert draft.overload
    assert all(e.kind == "assessment" for e in draft.entries) and sum(e.est_minutes for e in draft.entries) <= 60
    assert "practice" in {e.kind for e in draft.dropped}


def test_control_objectives_never_appear() -> None:  # AC-P2
    hidden = signal(mistake_severity="high", mastery_level=1)
    draft = build_plan(
        [hidden, signal(mastery_level=1)], capacity_minutes=120, control_objectives={hidden.objective_id}
    )
    assert hidden.objective_id not in {e.objective_id for e in [*draft.entries, *draft.dropped]}
    assert draft.excluded_control == 1


# --- Phase 3: reinforcement from an external class (AC-X9, AC-X10) -------------------------------------------


def test_an_external_weakness_becomes_a_reinforcement_item() -> None:
    entry = entry_for(signal(external_weakness=True, mastery_level=3))
    assert entry is not None
    assert (entry.kind, entry.reason_code, entry.est_minutes) == ("reinforcement", "external_class_gap", 20)


def test_school_and_exam_work_outrank_an_external_class() -> None:
    """Complement, never duplicate: the IGCSE day comes first, the external programme fills what is left."""
    assert entry_for(signal(external_weakness=True, assessment_due=True)).kind == "assessment"  # type: ignore[union-attr]
    assert entry_for(signal(external_weakness=True, school_topic=True)).kind == "school_topic"  # type: ignore[union-attr]
    assert entry_for(signal(external_weakness=True, mistake_severity="high")).kind == "mistake_fix"  # type: ignore[union-attr]


def test_at_most_one_reinforcement_item_a_day() -> None:  # AC-X9
    signals = [signal(external_weakness=True, mastery_level=2) for _ in range(4)]
    draft = build_plan(signals, capacity_minutes=240, control_objectives=set())
    assert sum(e.kind == "reinforcement" for e in draft.entries) == 1
    assert sum(e.kind == "reinforcement" for e in draft.dropped) == 3
    assert all(e.est_minutes <= 20 for e in draft.entries if e.kind == "reinforcement")


def test_reinforcement_is_dropped_on_a_full_day() -> None:
    signals = [
        signal(external_weakness=True, mastery_level=2),
        signal(assessment_due=True, mastery_level=1),
        signal(mistake_severity="high", mastery_level=1),
    ]
    draft = build_plan(signals, capacity_minutes=30, control_objectives=set())
    assert all(e.kind != "reinforcement" for e in draft.entries)


def test_the_traces_own_order_decides_between_equal_candidates() -> None:
    best, second = signal(external_weakness=True, external_rank=0), signal(external_weakness=True, external_rank=1)
    assert priority(best) > priority(second)
    draft = build_plan([second, best], capacity_minutes=240, control_objectives=set())
    kept = [e for e in draft.entries if e.kind == "reinforcement"]
    assert [e.objective_id for e in kept] == [best.objective_id]
