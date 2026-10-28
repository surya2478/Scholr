"""Unit tests for the Metacognitive Calibration Engine (pure calculations & profile aggregation)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.assessment.service import ConfidenceAttempt
from app.modules.evaluation.service import EvaluationSummary
from app.modules.progress.metacognition import (
    calculate_brier_calibration,
    classify_quadrant,
    derive_advice,
    get_metacognitive_profile,
)


def test_classify_quadrant_all_four_cells() -> None:
    # Quadrant 1: True Mastery (High confidence >= 3, High score >= 0.70)
    assert classify_quadrant(confidence=4, accuracy=1.0) == "true_mastery"
    assert classify_quadrant(confidence=3, accuracy=0.70) == "true_mastery"

    # Quadrant 2: Dangerous Blindspot (High confidence >= 3, Low score < 0.70)
    assert classify_quadrant(confidence=4, accuracy=0.0) == "dangerous_blindspot"
    assert classify_quadrant(confidence=3, accuracy=0.69) == "dangerous_blindspot"

    # Quadrant 3: Hesitant Mastery (Low confidence <= 2, High score >= 0.70)
    assert classify_quadrant(confidence=1, accuracy=0.85) == "hesitant_mastery"
    assert classify_quadrant(confidence=2, accuracy=0.70) == "hesitant_mastery"

    # Quadrant 4: Known Gap (Low confidence <= 2, Low score < 0.70)
    assert classify_quadrant(confidence=1, accuracy=0.0) == "known_gap"
    assert classify_quadrant(confidence=2, accuracy=0.50) == "known_gap"


def test_calculate_brier_calibration() -> None:
    # Empty list returns 100.0%
    assert calculate_brier_calibration([]) == 100.0

    # Perfect predictions: confidence matches accuracy
    perfect = [(0.95, 0.95), (0.75, 0.75)]
    assert calculate_brier_calibration(perfect) == 100.0

    # Extreme overconfidence: 95% confident, 0% score -> MSE = 0.95^2 = 0.9025
    terrible = [(0.95, 0.0)]
    score = calculate_brier_calibration(terrible)
    assert round(score, 1) == 9.8


def test_derive_advice_logic() -> None:
    # Under 3 total attempts
    rating, advice = derive_advice(total=2, blindspot_pct=50.0, hesitant_pct=0.0, calibration_score=60.0)
    assert rating == "Gathering Data"
    assert "at least 3 practice questions" in advice

    # High blindspots >= 25%
    rating, advice = derive_advice(total=10, blindspot_pct=30.0, hesitant_pct=10.0, calibration_score=65.0)
    assert rating == "Overconfidence Vulnerability"
    assert "sanity-check" in advice

    # High hesitant >= 30%
    rating, advice = derive_advice(total=10, blindspot_pct=10.0, hesitant_pct=40.0, calibration_score=70.0)
    assert rating == "Hesitant Competence"
    assert "Trust your preparation" in advice

    # High calibration score >= 75%
    rating, advice = derive_advice(total=10, blindspot_pct=10.0, hesitant_pct=10.0, calibration_score=85.0)
    assert rating == "High Metacognitive Calibration"


def test_get_metacognitive_profile_aggregation(monkeypatch) -> None:  # noqa: ANN001
    student_id = uuid4()
    subject_id = uuid4()
    att1_id = uuid4()
    att2_id = uuid4()
    att3_id = uuid4()
    att4_id = uuid4()

    mock_attempts = [
        ConfidenceAttempt(
            id=att1_id,
            question_item_id=uuid4(),
            subject_id=subject_id,
            question_stem="Calculate the gradient",
            pre_confidence=4,
            max_assistance_level=0,
            submitted_at=datetime.now(UTC),
        ),
        ConfidenceAttempt(
            id=att2_id,
            question_item_id=uuid4(),
            subject_id=subject_id,
            question_stem="Factorise 6x^2 + 7x - 5",
            pre_confidence=4,
            max_assistance_level=1,
            submitted_at=datetime.now(UTC),
        ),
        ConfidenceAttempt(
            id=att3_id,
            question_item_id=uuid4(),
            subject_id=subject_id,
            question_stem="Find the angle theta",
            pre_confidence=2,
            max_assistance_level=0,
            submitted_at=datetime.now(UTC),
        ),
        ConfidenceAttempt(
            id=att4_id,
            question_item_id=uuid4(),
            subject_id=subject_id,
            question_stem="Solve simultaneous equations",
            pre_confidence=1,
            max_assistance_level=3,
            submitted_at=datetime.now(UTC),
        ),
    ]

    mock_evals = {
        att1_id: EvaluationSummary(uuid4(), "final", 4.0, 4.0, ()),  # True Mastery
        att2_id: EvaluationSummary(uuid4(), "final", 1.0, 4.0, ("Dropped negative sign",)),  # Dangerous Blindspot
        att3_id: EvaluationSummary(uuid4(), "final", 3.0, 3.0, ()),  # Hesitant Mastery
        att4_id: EvaluationSummary(uuid4(), "final", 0.0, 4.0, ("Formula forgotten",)),  # Known Gap
    }

    monkeypatch.setattr(
        "app.modules.assessment.service.attempts_with_confidence",
        lambda _s, student_id, subject_id=None, limit=100: mock_attempts,
    )
    monkeypatch.setattr(
        "app.modules.evaluation.service.evaluation_summaries_for_attempts",
        lambda _s, attempt_ids: mock_evals,
    )

    mock_session = MagicMock()
    profile = get_metacognitive_profile(mock_session, student_id=student_id, subject_id=subject_id)

    assert profile.total_evaluated_with_confidence == 4
    assert profile.quadrants["true_mastery"].count == 1
    assert profile.quadrants["dangerous_blindspot"].count == 1
    assert profile.quadrants["hesitant_mastery"].count == 1
    assert profile.quadrants["known_gap"].count == 1
    assert len(profile.blindspots) == 1
    assert profile.blindspots[0].attempt_id == att2_id
    assert "Dropped negative sign" in profile.blindspots[0].mistakes
    assert profile.independence.independence_index == 75.0
    assert profile.independence.tier == "Self-Reliant"
    assert profile.independence.unassisted_count == 2
    assert profile.independence.nudged_count == 1
    assert profile.independence.assisted_count == 1


def test_rated_but_not_yet_marked_attempts_do_not_break_the_profile(monkeypatch) -> None:  # noqa: ANN001
    """Review of 22 Sep 2026: with confidence ratings but no evaluation yet, the profile was built without its
    required `independence` block and the endpoint failed."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.modules.assessment import service as assessment
    from app.modules.evaluation import service as evaluation
    from app.modules.progress import metacognition

    attempt = assessment.ConfidenceAttempt(uuid4(), uuid4(), uuid4(), "stem", 4, 0, datetime.now(UTC))
    monkeypatch.setattr(assessment, "attempts_with_confidence", lambda *a, **k: [attempt])
    monkeypatch.setattr(evaluation, "evaluation_summaries_for_attempts", lambda *a, **k: {})
    monkeypatch.setattr(metacognition.curriculum, "exam_seconds_per_mark", lambda *a, **k: {})
    profile = metacognition.get_metacognitive_profile(None, student_id=uuid4())  # type: ignore[arg-type]
    assert profile.total_evaluated_with_confidence == 0 and profile.independence.total == 1
    assert profile.velocity is not None
    assert profile.velocity.speed_trap_count == 0


def test_velocity_is_judged_against_her_own_papers_pace() -> None:
    from app.modules.progress.metacognition import classify_velocity

    pace = 72.0  # Maths 0580: 120 minutes for 100 marks
    assert classify_velocity(None, 4, 5, pace) == "untracked"
    assert classify_velocity(0, 4, 5, pace) == "untracked"
    assert classify_velocity(300, 4, 5, None) == "untracked"  # no timed paper for the subject: nothing guessed
    # 5 marks allow 360 s.
    assert classify_velocity(300, 4, 5, pace) == "optimal_flow"
    assert classify_velocity(400, 4, 5, pace) == "hesitant_success"
    assert classify_velocity(150, 1, 5, pace) == "speed_trap"  # marks lost in under half the time
    assert classify_velocity(300, 1, 5, pace) == "time_sink"


def test_derive_velocity_stats() -> None:
    from app.modules.progress.metacognition import derive_velocity_stats
    from app.modules.progress.schemas import MetacognitionItem

    now = datetime.now(UTC)

    def item(marks: int, awarded: int, seconds: int, category: str) -> MetacognitionItem:
        return MetacognitionItem(
            attempt_id=uuid4(), subject_id=uuid4(), question_stem="Q", pre_confidence=4, confidence_label="Very sure",
            marks_awarded=awarded, marks_available=marks, percentage=awarded * 100 // marks, quadrant="true_mastery",
            mistakes=[], submitted_at=now, time_spent_s=seconds, velocity_category=category,  # type: ignore[arg-type]
        )  # fmt: skip

    stats = derive_velocity_stats([item(4, 4, 120, "optimal_flow"), item(4, 0, 40, "speed_trap")], [288.0, 288.0])
    assert (stats.optimal_flow_count, stats.speed_trap_count, stats.time_sink_count) == (1, 1, 0)
    assert stats.average_seconds_per_mark == 20.0
    assert stats.exam_time_used_percent == 28  # 160 s of the 576 s her papers allow
    assert stats.quadrants["optimal_flow"].percentage == 50.0
    assert "trick" not in stats.diagnosis
    empty = derive_velocity_stats([], [])
    assert empty.exam_time_used_percent is None and empty.speed_trap_count == 0
