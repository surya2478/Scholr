"""essay_levels pipeline (ARCHITECTURE §12.2) with scripted markers: dual marking, agreement, calibration gate."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.llm.gateway import CallContext
from app.modules.evaluation.essay_levels import EssayInput, evaluate, guide_for
from app.tools.text_checks import check_answer
from tests.fixtures.llm import scripted_gateway

CTX = CallContext(request_id="test", tenant_id=uuid4())
# Fixture question and answers written for these tests.
ANSWER = (
    "Formal social control is carried out by agencies such as the police and courts. Courts punish offenders with "
    "sentences, which deters others. In conclusion courts are effective but only for people who are caught."
)


def essay(**overrides: Any) -> EssayInput:
    values: dict[str, Any] = {
        "marks": 4,
        "stem": "Explain two ways courts act as agencies of formal social control.",
        "context": None,
        "command_word": "explain",
        "mark_scheme": "One mark per way identified, one mark per way developed.",
        "answer": ANSWER,
        "evaluator_role": "essay_marker_a",
        "second_evaluator_role": "essay_marker_b",
        "dual_marking": True,
        "max_disagreement": {"short_answer_marks": 1, "essay_levels": 0},
        "confidence_threshold": 0.8,
        "calibrated": True,
        "level_guide": {"points": "point guide", "14": "levels guide for 14"},
        "mistake_categories": ("evidence", "command_word"),
        "mistake_labels": ("no_evidence",),
    }
    values.update(overrides)
    return EssayInput(**values)


def marking(marks: int, level: int | None = None, confidence: float = 0.9, **extra: Any) -> dict[str, Any]:
    return {
        "marks_awarded": marks,
        "level": level,
        "ao_marks": {"AO1": marks, "AO2": 0, "AO3": 0},
        "credited_points": ["courts punish offenders"],
        "missing": [],
        "feedback_summary": "Clear points about sentencing.",
        "what_went_well": "Uses the term formal social control.",
        "next_step": "Develop the second way with an example.",
        "mistakes": [
            {"category": "evidence", "label": "no_evidence", "severity": "medium", "description": "No example."}
        ],
        "confidence": confidence,
        **extra,
    }


def test_text_checks() -> None:
    checks = check_answer(ANSWER, marks=14, command_word=None, stem="Evaluate the view that courts work.")
    assert checks.command_word == "evaluate" and checks.judgement_expected and checks.conclusion_present
    assert check_answer("too short", marks=8, command_word="discuss").too_short


def test_agreeing_markers_give_a_final_conservative_mark() -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply(marking(3))
    transport.reply(marking(4))
    outcome = evaluate(gateway, CTX, essay())
    assert (outcome.status, outcome.marks_awarded, len(outcome.markers)) == ("final", 3, 2)
    assert outcome.mistakes[0]["fingerprint"] == "evidence:no_evidence"
    assert len(transport.requests) == 2


def test_uncalibrated_evaluator_is_always_provisional() -> None:  # AC-E5
    gateway, transport, _ = scripted_gateway()
    transport.reply(marking(3))
    transport.reply(marking(3))
    outcome = evaluate(gateway, CTX, essay(calibrated=False))
    assert outcome.status == "needs_review" and "evaluator_not_calibrated" in outcome.issues
    assert outcome.confidence <= 0.5


def test_disagreement_and_level_rules() -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply(marking(1))
    transport.reply(marking(4))
    assert "marks_disagreement" in evaluate(gateway, CTX, essay()).issues

    gateway, transport, _ = scripted_gateway()
    transport.reply(marking(10, level=3, ao_marks={"AO1": 4, "AO2": 3, "AO3": 3}))
    transport.reply(marking(8, level=2, ao_marks={"AO1": 3, "AO2": 3, "AO3": 2}))
    levels = evaluate(gateway, CTX, essay(marks=14))
    assert "level_disagreement" in levels.issues and levels.level == 2
    assert guide_for(14, {"points": "p", "14": "levels"}) == ("levels", "levels")


def test_blank_answer_makes_no_call_and_second_marker_failure_needs_review() -> None:
    gateway, transport, _ = scripted_gateway()
    blank = evaluate(gateway, CTX, essay(answer="  "))
    assert (blank.status, blank.marks_awarded, transport.requests) == ("final", 0, [])

    gateway, transport, _ = scripted_gateway()
    transport.reply(marking(3))
    transport.fail("quota_exceeded")
    outcome = evaluate(gateway, CTX, essay())
    assert outcome.status == "needs_review" and "second_marker_unavailable" in outcome.issues
