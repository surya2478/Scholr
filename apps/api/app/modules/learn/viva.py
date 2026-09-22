"""Oral defence ("viva") on a real exam question (review of 22 Sep 2026; docs/STUDENT-APP.md §19).

She works through an approved walkthrough (AC-U16) one step at a time. Before each step is shown she says or
types what she would do next and why; a model compares her explanation with that step — and only that step — and
code checks the verdict before she sees it:

- an explanation of a couple of words is "not yet", whatever the model says;
- "right" needs her numbers, where she gives any, to agree with the step's own results;
- a hint for a step she has not got yet may not give away that step's results, or any later step's.

The verdict is feedback on her reasoning, never a mark: it is recorded as a `self_explanation_given` event, which
mastery does not read.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

Verdict = Literal["right", "partly", "not_yet"]
MIN_WORDS = 3
FIELD_CHARS = 400
_MATH = re.compile(r"\$([^$]+)\$")
# A number, including one that ends a sentence ("You should get 18.").
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?!\w|\.\d)")
_RESULT = re.compile(r"=\s*(-?\d+(?:\.\d+)?)")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
TOO_SHORT_HINT = "Say a little more: what would you write next, and why?"
NUMBERS_HINT = "Your method sounds right — check your numbers against it."
GENERIC_HINT = "Think about which fact or formula this step needs, and how the question's numbers fit it."


class VivaJudgement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verdict: Verdict
    what_was_right: str = ""
    missing: str = ""
    hint: str = ""


def _numbers(text: str) -> list[float]:
    return [float(n) for n in _NUMBER.findall(text.replace("−", "-"))]


def step_results(step_text: str) -> list[float]:
    """The values a step arrives at: every number straight after an "=" in it ("$2 \\times 9 = 18$" -> 18)."""
    plain = _MATH.sub(lambda m: m.group(1), step_text).replace("−", "-")
    return [float(n) for n in _RESULT.findall(plain)]


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.01, 0.005 * abs(b))


def _clean(text: str) -> str:
    return " ".join(_CONTROL.sub(" ", text).split())[:FIELD_CHARS]


def _leaks(text: str, secrets: Sequence[float]) -> bool:
    # 0 and 1 are too common to count as giving a result away.
    return any(_close(n, s) for n in _numbers(text) for s in secrets if s not in (0, 1))


def new_numbers(step_text: str, known: str) -> list[float]:
    """Numbers a step introduces: its results after "=", and any number it states that the question and the steps
    before it do not ("These numbers are -8 and +6" has no "=", and gives the step away just the same)."""
    given = _numbers(known)
    stated = _numbers(_MATH.sub(lambda m: m.group(1), step_text))
    # Compared by size: "x^2 - 2x - 48 = 0" gives 48 and 2, which a step writes as -48 and -2.
    fresh = [n for n in stated if not any(_close(abs(n), abs(g)) for g in given)]
    return list(dict.fromkeys([*step_results(step_text), *fresh]))


def guard(
    judgement: VivaJudgement,
    *,
    explanation: str,
    step_text: str,
    later_steps: Sequence[str],
    known: str = "",
) -> VivaJudgement:
    """What she sees: the model's verdict, held to the three rules in the module docstring. `known` is the question
    and the steps already shown: numbers from there are hers to use, not secrets."""
    verdict: Verdict = judgement.verdict
    right, missing, hint = _clean(judgement.what_was_right), _clean(judgement.missing), _clean(judgement.hint)
    if len(explanation.split()) < MIN_WORDS and not _numbers(explanation):
        return VivaJudgement(verdict="not_yet", what_was_right="", missing="", hint=TOO_SHORT_HINT)
    results = new_numbers(step_text, known)
    said = [n for n in _numbers(explanation) if not any(_close(abs(n), abs(g)) for g in _numbers(known))]
    if verdict == "right" and results and said and not any(_close(n, r) for n in said for r in results):
        verdict, missing, hint = "partly", missing or "Your numbers do not match this step.", NUMBERS_HINT
    if verdict != "right":
        secrets = [*results, *(r for later in later_steps for r in new_numbers(later, known))]
        if _leaks(missing, secrets):
            missing = "Part of this step is still missing."
        if _leaks(hint, secrets) or not hint:
            hint = GENERIC_HINT
    return VivaJudgement(verdict=verdict, what_was_right=right, missing=missing, hint=hint)
