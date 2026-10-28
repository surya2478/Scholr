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
from app.modules.curriculum import service as curriculum
from app.modules.evaluation import service as evaluation
from app.modules.progress.schemas import (
    IndependenceStats,
    MetacognitionItem,
    MetacognitionOut,
    QuadrantCount,
    VelocityQuadrant,
    VelocityStats,
)

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


VelocityCategory = Literal["optimal_flow", "speed_trap", "time_sink", "hesitant_success", "untracked"]
# Rushed: marks lost in under half the time the paper allows for them.
RUSHED_SHARE = 0.5


def classify_velocity(
    time_spent_s: int | None, marks_awarded: float, marks_available: int, exam_seconds_per_mark: float | None
) -> VelocityCategory:
    """Where an answer falls on time against accuracy. The pace is her own subject's papers' (minutes allowed over
    marks), not a general rule; with no timing or no timed paper the answer is "untracked".

    - right (>= 70%) within the time the paper allows: optimal_flow
    - right, but over that time: hesitant_success
    - marks lost in under half that time: speed_trap (rushed)
    - marks lost, taking longer: time_sink
    """
    if not time_spent_s or time_spent_s <= 0 or marks_available <= 0 or not exam_seconds_per_mark:
        return "untracked"
    allowed = exam_seconds_per_mark * marks_available
    if marks_awarded / marks_available >= MASTERY_ACCURACY_THRESHOLD:
        return "optimal_flow" if time_spent_s <= allowed else "hesitant_success"
    return "speed_trap" if time_spent_s <= allowed * RUSHED_SHARE else "time_sink"


def derive_velocity_stats(items: Sequence[MetacognitionItem], allowed_s: Sequence[float]) -> VelocityStats:
    """Counts per category, and her time against the time her papers allow (``allowed_s``: one per tracked item)."""
    tracked = [it for it in items if it.velocity_category != "untracked" and it.time_spent_s]
    counts = {k: sum(1 for it in tracked if it.velocity_category == k) for k in VELOCITY_KEYS}
    total = len(tracked)
    quadrants = {
        k: VelocityQuadrant(count=n, percentage=round(n / total * 100, 1) if total else 0.0) for k, n in counts.items()
    }
    used = sum(it.time_spent_s or 0 for it in tracked)
    marks = sum(it.marks_available for it in tracked)
    return VelocityStats(
        speed_trap_count=counts["speed_trap"],
        time_sink_count=counts["time_sink"],
        optimal_flow_count=counts["optimal_flow"],
        hesitant_count=counts["hesitant_success"],
        average_seconds_per_mark=round(used / marks, 1) if marks else 0.0,
        exam_time_used_percent=round(used / sum(allowed_s) * 100) if total and sum(allowed_s) else None,
        quadrants=quadrants,
        diagnosis=_velocity_diagnosis(counts, total),
    )


VELOCITY_KEYS = ("optimal_flow", "speed_trap", "time_sink", "hesitant_success")


def _velocity_diagnosis(counts: dict[str, int], total: int) -> str:
    if total == 0:
        return "Answer a few questions and the time you take will show here, against the time your exam allows."
    if counts["speed_trap"] >= 2 and counts["speed_trap"] >= counts["time_sink"]:
        return (
            "Several answers that lost marks took less than half the time the exam allows for them. "
            "Reading the question again before you answer may help."
        )
    if counts["time_sink"] >= 2:
        return (
            "Several questions took longer than the exam allows and still lost marks. In an exam, it can be "
            "better to move on and come back to them at the end."
        )
    if counts["hesitant_success"] >= 2:
        return "Your answers are mostly right but often take longer than the exam allows. Timed practice will help."
    if counts["optimal_flow"] >= total / 2:
        return "Most of your answers were right and within the time the exam allows."
    return "No clear pattern yet — it will show as you answer more questions."


def _empty_profile(student_id: UUID, attempts: Sequence[assessment.ConfidenceAttempt]) -> MetacognitionOut:
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
        independence=derive_independence(attempts),
        velocity=derive_velocity_stats([], []),
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
        return _empty_profile(student_id, attempts)

    eval_map = evaluation.evaluation_summaries_for_attempts(s, [a.id for a in attempts])
    paces = curriculum.exam_seconds_per_mark(s, list({a.subject_id for a in attempts}))
    allowed_s: list[float] = []

    items: list[MetacognitionItem] = []
    pairs_for_brier: list[tuple[float, float]] = []

    for att in attempts:
        ev = eval_map.get(att.id)
        if not ev or ev.marks_available <= 0:
            continue

        acc = min(1.0, max(0.0, ev.marks_awarded / ev.marks_available))
        conf_prob = CONFIDENCE_PROBABILITIES.get(att.pre_confidence, 0.5)
        quad = classify_quadrant(att.pre_confidence, acc)
        vel_cat = classify_velocity(att.time_spent_s, ev.marks_awarded, ev.marks_available, paces.get(att.subject_id))
        if vel_cat != "untracked":
            allowed_s.append(paces[att.subject_id] * ev.marks_available)

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
                time_spent_s=att.time_spent_s,
                velocity_category=vel_cat,
            )
        )

    total = len(items)
    if total == 0:
        # Rated but not yet marked: this path once omitted `independence` and the endpoint failed (review, 22 Sep).
        return _empty_profile(student_id, attempts)

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
        velocity=derive_velocity_stats(items, allowed_s),
    )
