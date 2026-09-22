"""Unit tests for the Chief Examiner Cognitive Bug-Hunting Challenge Engine."""

from __future__ import annotations

from app.modules.mistakes.challenges import (
    BugVerificationIn,
    get_challenge,
    list_challenges,
    verify_challenge,
)


def test_list_and_filter_challenges() -> None:
    all_challenges = list_challenges()
    assert len(all_challenges) >= 4

    math_challenges = list_challenges("math_sciences")
    assert len(math_challenges) >= 3
    assert all(c.subject_category == "math_sciences" for c in math_challenges)

    physics_challenges = list_challenges("physical_sciences")
    assert len(physics_challenges) >= 1

    soc_challenges = list_challenges("social_sciences")
    assert len(soc_challenges) >= 1


def test_verify_challenge_correct_diagnosis() -> None:
    challenge = get_challenge("bug-math-01")
    assert challenge is not None

    # Correct step (2) and correct bug type ("conceptual")
    sub = BugVerificationIn(
        selected_step=2,
        selected_bug_type="conceptual",
        award_method_mark=False,
    )
    result = verify_challenge("bug-math-01", sub)
    assert result.correct_step is True
    assert result.correct_type is True
    assert result.success is True
    assert result.score == 100
    assert "fatal breakdown" in result.examiner_report


def test_verify_challenge_partial_diagnosis() -> None:
    # Correct step (2) but wrong classification
    sub = BugVerificationIn(
        selected_step=2,
        selected_bug_type="vocabulary",
        award_method_mark=False,
    )
    result = verify_challenge("bug-math-01", sub)
    assert result.correct_step is True
    assert result.correct_type is False
    # Step and method-mark decision right (bug-math-01 earns no M1), type wrong: 50 + 25 (22 Sep 2026 scoring).
    assert result.success is True
    assert result.score == 75


def test_verify_challenge_wrong_step() -> None:
    # Selected benign step 1
    sub = BugVerificationIn(
        selected_step=1,
        selected_bug_type="conceptual",
        award_method_mark=True,
    )
    result = verify_challenge("bug-math-01", sub)
    assert result.correct_step is False
    assert result.success is False
    assert result.score == 25  # only the error type is right; awarding M1 here is wrong


def test_the_method_mark_decision_counts_and_an_unknown_challenge_is_404() -> None:
    """Review of 22 Sep 2026: her award_method_mark answer was asked for and never checked."""
    import pytest

    from app.core.errors import ApiError
    from app.modules.mistakes import challenges
    from app.modules.mistakes.challenges import BugVerificationIn

    # bug-math-02: the bug is step 2, a calculation slip, and the method mark M1 stands.
    right = challenges.verify_challenge(
        "bug-math-02", BugVerificationIn(selected_step=2, selected_bug_type="calculation", award_method_mark=True)
    )
    assert (right.success, right.score, right.correct_mark) == (True, 100, True)
    wrong_mark = challenges.verify_challenge(
        "bug-math-02", BugVerificationIn(selected_step=2, selected_bug_type="calculation", award_method_mark=False)
    )
    assert (wrong_mark.success, wrong_mark.score, wrong_mark.correct_mark) == (False, 75, False)
    with pytest.raises(ApiError) as err:
        challenges.verify_challenge(
            "no-such-challenge", BugVerificationIn(selected_step=1, selected_bug_type="x", award_method_mark=True)
        )
    assert err.value.status == 404
