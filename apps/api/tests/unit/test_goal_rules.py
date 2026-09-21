"""Goal measures (AC-G1): progress is derived, reads correctly in both directions, and refuses empty goals."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.goals import rules

TODAY = date(2026, 9, 16)


def test_progress_from_a_baseline_not_from_zero() -> None:
    """Without a baseline, "6 of 8 topics" looks like progress even if it started at 6."""
    moved = rules.progress(measure="topics_secure", current=6, target=8, baseline=4, target_date=None, today=TODAY)
    assert moved.share == 0.5 and not moved.reached

    stood_still = rules.progress(
        measure="topics_secure", current=6, target=8, baseline=6, target_date=None, today=TODAY
    )
    assert stood_still.share == 0.0, "no movement is no progress, however good the number looks"


def test_a_falling_measure_reads_the_right_way_round() -> None:
    """Open mistakes go down towards their target; 9 of 12 cleared is progress, not failure."""
    progress = rules.progress(measure="open_mistakes", current=3, target=0, baseline=12, target_date=None, today=TODAY)
    assert progress.direction == "fall"
    assert progress.share == 0.75 and not progress.reached

    done = rules.progress(measure="open_mistakes", current=0, target=0, baseline=12, target_date=None, today=TODAY)
    assert done.reached and done.share == 1.0


def test_going_backwards_never_shows_negative_progress() -> None:
    progress = rules.progress(measure="topics_secure", current=2, target=8, baseline=4, target_date=None, today=TODAY)
    assert progress.share == 0.0 and not progress.reached


def test_progress_is_capped_at_the_target() -> None:
    progress = rules.progress(measure="topics_secure", current=20, target=8, baseline=4, target_date=None, today=TODAY)
    assert progress.share == 1.0 and progress.reached


def test_no_baseline_means_no_claim_about_the_share() -> None:
    progress = rules.progress(
        measure="topics_secure", current=6, target=8, baseline=None, target_date=None, today=TODAY
    )
    assert progress.share is None
    assert not progress.reached


def test_days_left_counts_down_and_goes_negative_when_missed() -> None:
    ahead = rules.progress(
        measure="topics_secure", current=1, target=8, baseline=0, target_date=date(2026, 10, 1), today=TODAY
    )
    assert ahead.days_left == 15
    passed = rules.progress(
        measure="topics_secure", current=1, target=8, baseline=0, target_date=date(2026, 9, 1), today=TODAY
    )
    assert passed.days_left == -15, "a missed date is said, not hidden"


@pytest.mark.parametrize(
    ("measure", "target", "current", "ok"),
    [
        ("topics_secure", 8, 4, True),
        ("topics_secure", 4, 4, False),  # already there: nothing to work towards
        ("topics_secure", 2, 4, False),  # asks her to go backwards
        ("open_mistakes", 0, 5, True),
        ("open_mistakes", 5, 5, False),
        ("open_mistakes", 9, 5, False),  # asks for more mistakes
        ("answers_without_help", 80, 60, True),
        ("answers_without_help", 140, 60, False),  # not a possible percentage
        ("active_days_per_week", 5, 3, True),
    ],
)
def test_a_goal_has_to_ask_for_a_change(measure: str, target: float, current: float, ok: bool) -> None:
    assert rules.is_realistic(measure=measure, target=target, current=current) is ok  # type: ignore[arg-type]


def test_every_measure_is_described() -> None:
    """A measure with no label or unit would reach a screen as a bare number."""
    for measure, config in rules.MEASURES.items():
        assert config["label"] and config["unit"] and config["help"], measure
        assert config["direction"] in ("rise", "fall"), measure


def test_an_unknown_measure_is_refused_rather_than_guessed() -> None:
    with pytest.raises(KeyError):
        rules.measure_config("tries_harder")
