"""structured_math pipeline: tool/LLM consistency (AC-E2), confidence and status, next steps (AC-E7)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.llm.gateway import CallContext
from app.modules.evaluation.structured_math import (
    DEFAULT_NEXT_STEP,
    REENTER_NEXT_STEP,
    MathInput,
    evaluate,
)
from app.modules.mistakes.service import MISTAKE_TYPES
from tests.fixtures.llm import scripted_gateway, user_prompt

CTX = CallContext(request_id="req-test", tenant_id=uuid4())
SPEC = {"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3", "accept_ranges": []}


def math_input(**overrides: Any) -> MathInput:
    values: dict[str, Any] = {
        "marks": 2,
        "stem": "Find the circumference of a circle with radius 2 cm.",
        "context": None,
        "command_word": "Calculate",
        "answer_spec": SPEC,
        "mark_scheme": "M1 for 2 x pi x 2\nA1 12.6 or 12.57 or 4pi",
        "working": "2 x pi x 2",
        "final_answer": "12.6",
        "from_photo": False,
        "evaluator_role": "evaluator_a",
        "confidence_threshold": 0.75,
        "mistake_categories": tuple(MISTAKE_TYPES),
        "mistake_labels": ("premature_rounding", "wrong_formula"),
    }
    values.update(overrides)
    return MathInput(**values)


def marking(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "awards": [
            {"code": "M1", "awarded": True, "reason": "correct method"},
            {"code": "A1", "awarded": True, "reason": "correct answer"},
        ],
        "marks_awarded": 2,
        "final_answer_correct": True,
        "feedback_summary": "Well done.",
        "what_went_well": "Clear method.",
        "next_step": "Try a question on arc length.",
        "mistakes": [],
        "confidence": 0.85,
    }
    values.update(overrides)
    return values


def run(inp: MathInput, reply: dict[str, Any]):  # noqa: ANN201
    gateway, transport, _ = scripted_gateway()
    transport.reply(reply)
    return evaluate(gateway, CTX, inp), transport


def test_agreement_is_final_and_prompt_carries_tool_verdict() -> None:
    outcome, transport = run(math_input(), marking())
    assert outcome.status == "final"
    assert outcome.confidence == 0.9
    assert outcome.tool.status == "correct"
    assert outcome.tool_agreement == "agree"
    prompt = user_prompt(transport.requests[0])
    assert "status=correct" in prompt
    assert "<final_answer>12.6</final_answer>" in prompt


def test_llm_disagreeing_with_tool_goes_to_review() -> None:
    outcome, _ = run(math_input(), marking(final_answer_correct=False, marks_awarded=1, awards=[]))
    assert outcome.status == "needs_review"
    assert "tool_llm_disagreement" in outcome.issues
    assert outcome.confidence <= 0.5


def test_full_marks_for_wrong_answer_goes_to_review() -> None:
    outcome, _ = run(math_input(final_answer="12.4"), marking())
    assert outcome.tool.status == "incorrect"
    assert {"tool_llm_disagreement", "full_marks_with_wrong_final_answer"} <= set(outcome.issues)


def test_partial_marks_for_a_correct_final_answer_go_to_review() -> None:
    awards = [{"code": "M1", "awarded": False, "reason": "no working"}, {"code": "A1", "awarded": True, "reason": "ok"}]
    outcome, _ = run(math_input(working=None), marking(awards=awards, marks_awarded=1))
    assert outcome.status == "needs_review"
    assert "partial_marks_with_correct_final_answer" in outcome.issues


def test_award_codes_must_add_up() -> None:
    outcome, _ = run(math_input(), marking(marks_awarded=1))
    assert "award_sum_mismatch" in outcome.issues


def test_low_confidence_without_issues_goes_to_review() -> None:
    outcome, _ = run(math_input(), marking(confidence=0.6))
    assert outcome.issues == []
    assert outcome.status == "needs_review"


def test_unreadable_final_answer_asks_student_to_reenter() -> None:
    outcome, _ = run(math_input(final_answer="about twelve"), marking(final_answer_correct=False, marks_awarded=1))
    assert outcome.status == "needs_review"
    assert outcome.feedback["next_step"] == REENTER_NEXT_STEP


def test_missing_next_step_gets_default_and_photo_lowers_confidence() -> None:
    outcome, _ = run(math_input(from_photo=True), marking(next_step=""))
    assert outcome.feedback["next_step"] == DEFAULT_NEXT_STEP
    assert outcome.confidence == round(0.9 * 0.95, 3)


def test_unescaped_latex_in_model_json_is_repaired() -> None:
    # A TAB inside the model's JSON string: what "\times" becomes when the backslash is not escaped.
    outcome, _ = run(math_input(), marking(next_step="Check $3 \times 4$ again."))
    assert outcome.feedback["next_step"] == "Check $3 \\times 4$ again."


def test_full_marks_answer_records_no_mistakes() -> None:
    habit = {"category": "reasoning", "label": "incomplete_working", "severity": "low", "description": "No working."}
    outcome, _ = run(math_input(working=None), marking(mistakes=[habit]))
    assert outcome.status == "final"
    assert outcome.mistakes == []


def test_mistakes_get_stable_fingerprints_and_unknown_categories_are_flagged() -> None:
    mistakes = [
        {"category": "calculation", "label": "premature_rounding", "severity": "medium", "description": "d1"},
        {"category": "calculation", "label": "made_up_label", "severity": "low", "description": "d2"},
        {"category": "astrology", "label": "other", "severity": "low", "description": "d3"},
    ]
    outcome, _ = run(
        math_input(final_answer="12.4"),
        marking(
            awards=[{"code": "M1", "awarded": True, "reason": "r"}, {"code": "A1", "awarded": False, "reason": "r"}],
            marks_awarded=1,
            final_answer_correct=False,
            mistakes=mistakes,
        ),
    )
    assert [m["fingerprint"] for m in outcome.mistakes] == ["calculation:premature_rounding", "calculation:other"]
    assert "unknown_mistake_category" in outcome.issues
