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
    assert result.success is True  # Step was correct, score 60
    assert result.score == 60


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
    assert result.score == 40
