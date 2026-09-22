"""Bug Hunter (mistakes/challenges.py): challenges built from approved walkthroughs, with one SymPy-checked slip."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.modules.learn import service as learn
from app.modules.mistakes import challenges
from app.modules.mistakes.challenges import BugVerificationIn


def walkthrough(steps: list[tuple[str, str]], final: str = "18") -> learn.ApprovedWalkthrough:
    return learn.ApprovedWalkthrough(
        objective_id=uuid4(), code="1.6", statement="HCF", subject_id=uuid4(), item_id=uuid4(),
        source_ref="0580/22/MJ25/Q8", label="June 2025 · Paper 22 · Q8", context=None,
        stem="Find the HCF of 36 and 54.", marks=2, steps=tuple({"text": t, "mark": m} for t, m in steps),
        final_answer=final,
    )  # fmt: skip


HCF = walkthrough(
    [
        (r"$36 = 2 \times 2 \times 3 \times 3$ and $54 = 2 \times 3 \times 3 \times 3$.", ""),
        (r"Multiply the common primes: $2 \times 3 \times 3 = 18$.", "B2"),
    ]
)


def test_one_marked_step_gets_a_slip_sympy_confirms_and_nothing_else_is_wrong() -> None:
    built = challenges.build(HCF)
    assert built is not None and built.bug_step == 2 and (built.old_value, built.new_value) == ("18", "19")
    texts = [s.text for s in built.challenge.student_steps]
    assert "= 19$" in texts[1] and texts[0] == HCF.steps[0]["text"]  # only the slipped step changes
    assert built.challenge.final_answer == "19"  # the answer line follows the slip
    # The page is never told which step is wrong.
    assert "bug" not in built.challenge.model_dump_json().lower()


def test_no_challenge_without_a_marked_calculation_step() -> None:
    assert challenges.build(walkthrough([("Explain why the answer is prime.", "B1")])) is None


def test_the_verdict_follows_the_schemes_mark_convention(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(learn, "approved_walkthroughs", lambda *a, **k: [HCF])
    monkeypatch.setattr(challenges.assessment, "examiner_insights", lambda *a, **k: None)
    cid = str(HCF.objective_id)
    # B2 is for the correct value: the slip loses it.
    right = challenges.verify_challenge(
        None, cid, BugVerificationIn(selected_step=2, selected_bug_type="calculation", award_method_mark=False)
    )  # type: ignore[arg-type]  # noqa: E501
    assert (right.success, right.score, right.bug_step) == (True, 100, 2)
    assert "B2" in right.examiner_report and right.correct_text == HCF.steps[1]["text"]
    kept = challenges.verify_challenge(
        None, cid, BugVerificationIn(selected_step=2, selected_bug_type="calculation", award_method_mark=True)
    )  # type: ignore[arg-type]  # noqa: E501
    assert (kept.success, kept.score) == (False, 75)
    with pytest.raises(ApiError) as err:
        challenges.verify_challenge(
            None, str(uuid4()), BugVerificationIn(selected_step=1, selected_bug_type="x", award_method_mark=True)
        )  # type: ignore[arg-type]  # noqa: E501
    assert err.value.status == 404
