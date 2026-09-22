"""Metacognitive Calibration Engine: analyzes confidence ratings vs. evaluated performance.

Implements a 2x2 epistemic quadrant model (True Mastery, Dangerous Blindspot,
Hesitant Mastery, Known Gap) and a Brier-based calibration index to measure and
strengthen the student's metacognitive self-awareness for Cambridge and IIT exams.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.assessment import service as assessment
from app.modules.evaluation import service as evaluation
from app.modules.progress.schemas import IndependenceStats, MetacognitionItem, MetacognitionOut, QuadrantCount

CONFIDENCE_LABELS: dict[int, str] = {
    1: "Not sure",
    2: "A little",
    3: "Fairly",
    4: "Very sure",
}

# Normalized expected probability of correctness associated with each pre_confidence rating
CONFIDENCE_PROBABILITIES: dict[int, float] = {
    1: 0.20,
    2: 0.40,
    3: 0.75,
    4: 0.95,
}

MASTERY_ACCURACY_THRESHOLD = 0.70  # >= 70% of available marks considered mastery of the question


def classify_quadrant(
    confidence: int, accuracy: float
) -> Literal["true_mastery", "dangerous_blindspot", "hesitant_mastery", "known_gap"]:
    """Categorize an attempt into the 2x2 Metacognitive Matrix."""
    high_confidence = confidence >= 3
    is_mastered = accuracy >= MASTERY_ACCURACY_THRESHOLD

    if high_confidence and is_mastered:
        return "true_mastery"
    if high_confidence and not is_mastered:
        return "dangerous_blindspot"
    if not high_confidence and is_mastered:
        return "hesitant_mastery"
    return "known_gap"


def calculate_brier_calibration(items: Sequence[tuple[float, float]]) -> float:
    """Calculate calibration percentage from (normalized_confidence, accuracy) pairs.

    Uses Brier score metric: MSE between subjective confidence probability and objective accuracy.
    A score of 100% means perfect calibration (confidence perfectly matched outcome).
    """
    if not items:
        return 100.0

    mean_squared_error = sum((conf - acc) ** 2 for conf, acc in items) / len(items)
    # Clamp to [0, 1] then invert to percentage
    return round(max(0.0, min(100.0, (1.0 - mean_squared_error) * 100.0)), 1)


def derive_advice(
    total: int,
    blindspot_pct: float,
    hesitant_pct: float,
    calibration_score: float,
) -> tuple[str, str]:
    """Provide pedagogical insight based on the student's metacognitive calibration."""
    if total < 3:
        return (
            "Gathering Data",
            "Rate your confidence on at least 3 practice questions to reveal your metacognitive pattern.",
        )

    if blindspot_pct >= 25.0:
        return (
            "Overconfidence Vulnerability",
            (
                "Watch out for subtle exam traps! You frequently feel sure on questions where method marks "
                "or edge cases slip through. Take an extra 20 seconds to sanity-check your intermediate working."
            ),
        )

    if hesitant_pct >= 30.0:
        return (
            "Hesitant Competence",
            (
                "Trust your preparation more! You regularly score high marks even when rating your confidence low. "
                "Your instincts and revision foundation are stronger than you give yourself credit for."
            ),
        )

    if calibration_score >= 75.0:
        return (
            "High Metacognitive Calibration",
            (
                "Outstanding self-awareness! Your confidence accurately predicts your performance, "
                "preventing both careless errors and wasted exam time."
            ),
        )

    return (
        "Developing Calibration",
        (
            "Your self-monitoring is progressing well. "
            "Continue rating your confidence on every question to sharpen your exam intuition."
        ),
    )


def derive_independence(attempts: Sequence[assessment.ConfidenceAttempt]) -> IndependenceStats:
    """Calculate the Socratic Independence Index (Ix): percentage of attempts solved with Help Level <= 1."""
    total = len(attempts)
    if total == 0:
        return IndependenceStats(
            independence_index=100.0,
            tier="Silent Master",
            unassisted_count=0,
            nudged_count=0,
            assisted_count=0,
            total=0,
            advice="Solve practice questions without hints to build your Independence Index!",
        )

    unassisted = sum(1 for a in attempts if a.max_assistance_level == 0)
    nudged = sum(1 for a in attempts if a.max_assistance_level == 1)
    assisted = sum(1 for a in attempts if a.max_assistance_level >= 2)

    index = round(((unassisted + nudged) / total) * 100, 1)

    if index >= 85.0:
        tier = "Silent Master"
        advice = "Phenomenal exam readiness! You solve almost all questions with zero AI assistance."
    elif index >= 70.0:
        tier = "Self-Reliant"
        advice = "Great independence! You rely only on occasional nudges when tackling complex questions."
    elif index >= 50.0:
        tier = "Guided Explorer"
        advice = "Good progress. Try pausing for 60 seconds before clicking hints to train retrieval memory."
    else:
        tier = "Supported Apprentice"
        advice = "Notice your hint reliance. Challenge yourself to solve twin questions unassisted."

    return IndependenceStats(
        independence_index=index,
        tier=tier,
        unassisted_count=unassisted,
        nudged_count=nudged,
        assisted_count=assisted,
        total=total,
        advice=advice,
    )


def get_metacognitive_profile(
    s: Session,
    *,
    student_id: UUID,
    subject_id: UUID | None = None,
    limit: int = 100,
) -> MetacognitionOut:
    """Aggregate confidence attempts and their evaluations into a complete Metacognition profile."""
    attempts = assessment.attempts_with_confidence(s, student_id=student_id, subject_id=subject_id, limit=limit)
    if not attempts:
        return MetacognitionOut(
            student_id=student_id,
            total_evaluated_with_confidence=0,
            brier_calibration_score=100.0,
            calibration_rating="Gathering Data",
            quadrants={
                "true_mastery": QuadrantCount(count=0, percentage=0.0),
                "dangerous_blindspot": QuadrantCount(count=0, percentage=0.0),
                "hesitant_mastery": QuadrantCount(count=0, percentage=0.0),
                "known_gap": QuadrantCount(count=0, percentage=0.0),
            },
            blindspots=[],
            recent_items=[],
            advice="Rate your confidence on at least 3 practice questions to reveal your metacognitive pattern.",
            independence=derive_independence([]),
        )

    eval_map = evaluation.evaluation_summaries_for_attempts(s, [a.id for a in attempts])

    items: list[MetacognitionItem] = []
    pairs_for_brier: list[tuple[float, float]] = []

    for att in attempts:
        ev = eval_map.get(att.id)
        if not ev or ev.marks_available <= 0:
            continue

        acc = min(1.0, max(0.0, ev.marks_awarded / ev.marks_available))
        conf_prob = CONFIDENCE_PROBABILITIES.get(att.pre_confidence, 0.5)
        quad = classify_quadrant(att.pre_confidence, acc)

        pairs_for_brier.append((conf_prob, acc))

        items.append(
            MetacognitionItem(
                attempt_id=att.id,
                subject_id=att.subject_id,
                question_stem=att.question_stem,
                pre_confidence=att.pre_confidence,
                confidence_label=CONFIDENCE_LABELS.get(att.pre_confidence, "Unknown"),
                marks_awarded=ev.marks_awarded,
                marks_available=ev.marks_available,
                percentage=round(acc * 100),
                quadrant=quad,
                mistakes=list(ev.mistake_descriptions),
                submitted_at=att.submitted_at,
            )
        )

    total = len(items)
    if total == 0:
        return MetacognitionOut(
            student_id=student_id,
            total_evaluated_with_confidence=0,
            brier_calibration_score=100.0,
            calibration_rating="Gathering Data",
            quadrants={
                "true_mastery": QuadrantCount(count=0, percentage=0.0),
                "dangerous_blindspot": QuadrantCount(count=0, percentage=0.0),
                "hesitant_mastery": QuadrantCount(count=0, percentage=0.0),
                "known_gap": QuadrantCount(count=0, percentage=0.0),
            },
            blindspots=[],
            recent_items=[],
            advice="Rate your confidence on at least 3 practice questions to reveal your metacognitive pattern.",
        )

    counts = {
        "true_mastery": sum(1 for it in items if it.quadrant == "true_mastery"),
        "dangerous_blindspot": sum(1 for it in items if it.quadrant == "dangerous_blindspot"),
        "hesitant_mastery": sum(1 for it in items if it.quadrant == "hesitant_mastery"),
        "known_gap": sum(1 for it in items if it.quadrant == "known_gap"),
    }

    quadrants = {k: QuadrantCount(count=v, percentage=round((v / total) * 100, 1)) for k, v in counts.items()}

    brier_score = calculate_brier_calibration(pairs_for_brier)
    rating, advice = derive_advice(
        total,
        quadrants["dangerous_blindspot"].percentage,
        quadrants["hesitant_mastery"].percentage,
        brier_score,
    )

    blindspots = [it for it in items if it.quadrant == "dangerous_blindspot"]

    return MetacognitionOut(
        student_id=student_id,
        total_evaluated_with_confidence=total,
        brier_calibration_score=brier_score,
        calibration_rating=rating,
        quadrants=quadrants,
        blindspots=blindspots[:10],
        recent_items=items[:15],
        advice=advice,
        independence=derive_independence(attempts),
    )
