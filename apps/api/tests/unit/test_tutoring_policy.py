from datetime import UTC, datetime, timedelta

import pytest

from app.modules.tutoring.policy import (
    HelpLevel,
    help_after_miss,
    is_frustrated,
    requires_isomorphic_followup,
    respond_to_help_request,
    should_request_self_explanation,
)


@pytest.mark.parametrize(
    ("mastery", "expected"),
    [
        (1, [HelpLevel.HINT, HelpLevel.WORKED_EXAMPLE, HelpLevel.NEXT_STEP, HelpLevel.FULL_SOLUTION]),
        (2, [HelpLevel.HINT, HelpLevel.WORKED_EXAMPLE, HelpLevel.NEXT_STEP, HelpLevel.FULL_SOLUTION]),
        (3, [HelpLevel.NUDGE, HelpLevel.HINT, HelpLevel.WORKED_EXAMPLE, HelpLevel.FULL_SOLUTION]),
        (4, [HelpLevel.NUDGE, HelpLevel.NUDGE, HelpLevel.HINT, HelpLevel.NEXT_STEP]),
        (5, [HelpLevel.NUDGE, HelpLevel.NUDGE, HelpLevel.HINT, HelpLevel.NEXT_STEP]),
    ],
)
def test_escalation_table(mastery: int, expected: list[HelpLevel]) -> None:
    got = [help_after_miss(mastery_level=mastery, miss_number=n, current_max=HelpLevel.NONE) for n in range(1, 5)]
    assert got == expected


def test_fifth_miss_stays_at_last_step() -> None:
    assert help_after_miss(mastery_level=3, miss_number=7, current_max=HelpLevel.NONE) == HelpLevel.FULL_SOLUTION


def test_frustration_escalates_one_step_faster() -> None:
    assert (
        help_after_miss(mastery_level=2, miss_number=1, current_max=HelpLevel.NONE, frustrated=True)
        == HelpLevel.WORKED_EXAMPLE
    )


def test_help_never_goes_backwards_within_an_item() -> None:
    assert (
        help_after_miss(mastery_level=4, miss_number=1, current_max=HelpLevel.WORKED_EXAMPLE)
        == HelpLevel.WORKED_EXAMPLE
    )


def test_first_help_request_without_attempt_asks_for_attempt() -> None:
    d = respond_to_help_request(attempts_made=0, asks_without_attempt=0, current_max=HelpLevel.NONE)
    assert d.action == "ask_for_attempt"


def test_second_request_is_never_refused() -> None:
    d = respond_to_help_request(attempts_made=0, asks_without_attempt=1, current_max=HelpLevel.NONE)
    assert d.action == "give_help"
    assert d.level == HelpLevel.NUDGE


def test_frustrated_student_gets_help_immediately() -> None:
    d = respond_to_help_request(attempts_made=0, asks_without_attempt=0, current_max=HelpLevel.NONE, frustrated=True)
    assert d.action == "give_help"
    assert d.level == HelpLevel.HINT


def test_help_request_caps_at_full_solution() -> None:
    d = respond_to_help_request(attempts_made=3, asks_without_attempt=0, current_max=HelpLevel.FULL_SOLUTION)
    assert d.level == HelpLevel.FULL_SOLUTION


def test_isomorphic_followup_only_after_full_solution() -> None:
    assert requires_isomorphic_followup(HelpLevel.FULL_SOLUTION)
    assert not requires_isomorphic_followup(HelpLevel.NEXT_STEP)


def test_self_explanation_every_n() -> None:
    assert [should_request_self_explanation(n, 3) for n in range(0, 7)] == [
        False,
        False,
        False,
        True,
        False,
        False,
        True,
    ]


def test_is_frustrated() -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    times = [now - timedelta(minutes=m) for m in (1, 2, 4)]
    assert is_frustrated(times, now=now)
    assert not is_frustrated(times[:2], now=now)
    assert not is_frustrated([now - timedelta(minutes=m) for m in (1, 2, 9)], now=now)
    assert is_frustrated([], now=now, classifier_flag=True)
