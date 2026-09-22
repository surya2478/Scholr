"""The viva's checks on a model's verdict (docs/STUDENT-APP.md §19): no model call here."""

from __future__ import annotations

from app.modules.learn.viva import GENERIC_HINT, TOO_SHORT_HINT, VivaJudgement, guard, step_results

STEP = "Multiply the common prime factors: $2 \times 3 \times 3 = 18$."
LATER = ["So the HCF is $18$."]


def judged(verdict: str, explanation: str, **fields: str) -> VivaJudgement:
    return guard(VivaJudgement(verdict=verdict, **fields), explanation=explanation, step_text=STEP, later_steps=LATER)  # type: ignore[arg-type]


def test_a_steps_results_are_the_numbers_after_an_equals_sign() -> None:
    assert step_results(STEP) == [18.0]
    assert step_results("Draw the line $y = 10 - x$.") == [10.0]


def test_right_needs_her_numbers_to_agree_with_the_step() -> None:
    assert judged("right", "multiply the common factors 2, 3 and 3 to get 18").verdict == "right"
    assert judged("right", "multiply the shared prime factors together").verdict == "right"  # method, no numbers
    wrong = judged("right", "I multiply the common factors to get 12")
    assert wrong.verdict == "partly" and wrong.missing


def test_a_couple_of_words_is_not_yet_whatever_the_model_says() -> None:
    short = judged("right", "multiply", what_was_right="Great!")
    assert (short.verdict, short.hint, short.what_was_right) == ("not_yet", TOO_SHORT_HINT, "")


def test_a_hint_may_not_give_the_step_away() -> None:
    leaked = judged("not_yet", "I would add them all up together", hint="Is it 18?", missing="You should get 18.")
    assert leaked.hint == GENERIC_HINT and "18" not in leaked.missing
    kept = judged("partly", "I would multiply some of them together", hint="Which primes appear in both numbers?")
    assert kept.hint == "Which primes appear in both numbers?"


def test_a_step_without_an_equals_sign_is_still_protected() -> None:
    """13.3's first step, "These numbers are -8 and +6", has no "=": the numbers it introduces are still secret, and
    the question's own numbers (-48, -2) are hers to use."""
    step = "Find two numbers that multiply to -48 and add up to -2. These numbers are -8 and +6."
    known = "Use factorisation to solve the equation $x^2 - 2x - 48 = 0$."
    leak = guard(
        VivaJudgement(verdict="not_yet", hint="Try -8 and 6."),
        explanation="I would use the formula here",
        step_text=step,
        later_steps=[],
        known=known,
    )
    assert leak.hint == GENERIC_HINT
    fair = guard(
        VivaJudgement(verdict="not_yet", hint="Which two numbers multiply to -48 and add to -2?"),
        explanation="I would use the formula here",
        step_text=step,
        later_steps=[],
        known=known,
    )
    assert fair.hint == "Which two numbers multiply to -48 and add to -2?"
    wrong_pair = guard(
        VivaJudgement(verdict="right"),
        explanation="the numbers are -6 and 8",
        step_text=step,
        later_steps=[],
        known=known,
    )
    assert wrong_pair.verdict == "partly"
