"""Validation-study maths (PHASE-1 §5): gain, retention ratio, eligibility, engagement, decision rule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.studies.results import (
    Assignment,
    FormSitting,
    MarkedItem,
    TopicScore,
    arm_results,
    decide,
    engagement,
    normalized_gain,
    retention_ratio,
    topic_score,
)

T0 = datetime(2026, 10, 19, 16, tzinfo=UTC)
APP, CONTROL = frozenset({uuid4(), uuid4()}), frozenset({uuid4()})


def sitting(kind: str, days: int, app: float | None, control: float | None) -> FormSitting:
    return FormSitting(
        kind=kind,
        form_code={"baseline": "A", "post": "B", "retention": "C"}[kind],
        submitted_at=T0 + timedelta(days=days),
        items=(
            MarkedItem(frozenset({next(iter(APP))}), 12, app),
            MarkedItem(CONTROL, 12, control),
        ),
    )


def test_gain_and_retention_formulas() -> None:
    base, post = TopicScore(3, 12, False), TopicScore(9, 12, False)
    assert normalized_gain(base, post) == pytest.approx((0.75 - 0.25) / 0.75)
    assert normalized_gain(TopicScore(12, 12, False), post) is None
    assert retention_ratio(post, TopicScore(6, 12, False)) == pytest.approx(6 / 9)
    assert retention_ratio(TopicScore(0, 12, False), TopicScore(6, 12, False)) is None


def test_topic_score_uses_items_inside_the_topic_and_counts_overlaps() -> None:
    mixed = FormSitting(
        "baseline",
        "A",
        T0,
        (
            MarkedItem(frozenset(APP), 4, 2),
            MarkedItem(frozenset({next(iter(APP)), *CONTROL}), 4, 4),
            MarkedItem(frozenset(APP), 4, None),
        ),
    )
    score, overlapping = topic_score(mixed, APP)
    assert score == TopicScore(awarded=2, available=8, provisional=True) and overlapping == 1


def test_engagement_window() -> None:
    starts = [T0 + timedelta(days=d) for d in (-1, 1, 2, 3, 8, 9, 10, 30)]
    minutes = [(T0 + timedelta(days=d), 30) for d in (1, 2, 40)]
    per_week, hours = engagement(starts, minutes, start=T0, end=T0 + timedelta(days=14))
    assert per_week == pytest.approx(3.0) and hours == pytest.approx(1.0)
    assert engagement(starts, minutes, start=None, end=T0) == (None, 0.0)


def test_go_candidate_needs_gain_engagement_and_retention() -> None:
    assignments = [Assignment("P1", "app", APP), Assignment("P1", "control", CONTROL)]
    sittings = [sitting("baseline", 0, 4, 4), sitting("post", 28, 10, 6), sitting("retention", 56, 9, 5)]
    arms = arm_results(assignments, sittings)
    assert [a.eligible for a in arms] == [True, True]
    result = decide(arms, sessions_per_week=3.5, app_hours=10)
    assert result.decision == "go_candidate" and "needs_student_interview" in result.reasons
    assert result.gain_difference == pytest.approx(0.75 - 0.25)
    assert result.learning_per_hour == pytest.approx(0.05)

    assert decide(arms, sessions_per_week=2.0, app_hours=10).decision == "iterate"
    no_retention = arm_results(assignments, sittings[:2])
    assert decide(no_retention, sessions_per_week=3.5, app_hours=10).decision == "pending"


def test_other_outcomes() -> None:
    assignments = [Assignment("P1", "app", APP), Assignment("P1", "control", CONTROL)]
    flat = arm_results(assignments, [sitting("baseline", 0, 4, 4), sitting("post", 28, 5, 6)])
    assert decide(flat, sessions_per_week=4, app_hours=5).decision == "no_gain"
    small = arm_results(assignments, [sitting("baseline", 0, 4, 4), sitting("post", 28, 7, 6)])
    assert decide(small, sessions_per_week=4, app_hours=5).reasons[-1] == "gain_difference_below_0.15"
    pending = arm_results(assignments, [sitting("baseline", 0, None, 1)])
    outcome = decide(pending, sessions_per_week=None, app_hours=0)
    assert outcome.decision == "pending" and outcome.provisional and "topic_baseline_outside_20_70" in outcome.reasons
