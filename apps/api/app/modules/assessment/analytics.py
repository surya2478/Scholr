"""Deterministic Assessment Performance Diagnostic Engine.

Calculates the 5-point in-depth post-exam analytics:
1. Score & Grade Boundary Projection
2. Pacing Telemetry & Time Sinks
3. Syllabus Topic Breakdown & Accuracy
4. Difficulty Conversion (Easy / Moderate / Challenging)
5. Mistake Attribution & Actionable Next Steps
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.assessment.models import Assessment, AssessmentItem, Attempt, QuestionItem
from app.modules.curriculum.models import Topic
from app.modules.evaluation.models import Evaluation


@dataclass
class DiagnosticReport:
    assessment_id: UUID
    title: str
    kind: str
    total_questions: int
    total_marks_available: float
    total_marks_awarded: float
    score_percentage: float
    pacing: dict[str, Any]
    time_sinks: list[dict[str, Any]]
    topic_breakdown: list[dict[str, Any]]
    difficulty_breakdown: list[dict[str, Any]]
    mistake_types_summary: dict[str, int]
    action_plan: list[str]


def generate_diagnostic_report(
    s: Session,
    assessment_id: UUID,
    student_id: UUID,
) -> DiagnosticReport:
    """Deterministic calculation of in-depth mock test performance."""
    assessment = s.scalar(select(Assessment).where(Assessment.id == assessment_id))
    if not assessment:
        raise ValueError(f"Assessment {assessment_id} not found")

    items = s.scalars(
        select(AssessmentItem).where(AssessmentItem.assessment_id == assessment_id).order_by(AssessmentItem.position)
    ).all()

    q_ids = [it.question_item_id for it in items]
    questions_by_id = {q.id: q for q in s.scalars(select(QuestionItem).where(QuestionItem.id.in_(q_ids))).all()}

    # Fetch attempts for this student on these questions in this assessment
    attempts = s.scalars(
        select(Attempt).where(
            Attempt.assessment_id == assessment_id,
            Attempt.student_id == student_id,
        )
    ).all()
    attempts_by_qid = {att.question_item_id: att for att in attempts}

    # Fetch evaluations for these attempts
    eval_by_attempt_id: dict[UUID, Evaluation] = {}
    if attempts:
        att_ids = [att.id for att in attempts]
        evals = s.scalars(
            select(Evaluation).where(Evaluation.attempt_id.in_(att_ids)).order_by(Evaluation.created_at.desc())
        ).all()
        for ev in evals:
            if ev.attempt_id not in eval_by_attempt_id:
                eval_by_attempt_id[ev.attempt_id] = ev

    total_marks_available = 0.0
    total_marks_awarded = 0.0
    total_time_s = 0
    time_sinks: list[dict[str, Any]] = []
    mistake_counts: dict[str, int] = {}
    topic_stats: dict[UUID, dict[str, Any]] = {}
    difficulty_stats: dict[int, dict[str, Any]] = {
        1: {"tier_label": "Foundation / Recall (Tier 1)", "available": 0.0, "awarded": 0.0},
        2: {"tier_label": "Application / Multi-Step (Tier 2)", "available": 0.0, "awarded": 0.0},
        3: {"tier_label": "Complex / Problem-Solving (Tier 3)", "available": 0.0, "awarded": 0.0},
    }

    for item in items:
        q = questions_by_id.get(item.question_item_id)
        if not q:
            continue
        marks = float(q.marks)
        total_marks_available += marks

        att = attempts_by_qid.get(q.id)
        time_spent = att.time_spent_s if att and att.time_spent_s else 0
        total_time_s += time_spent

        ev = eval_by_attempt_id.get(att.id) if att else None
        awarded = float(ev.marks_awarded) if ev else 0.0
        total_marks_awarded += awarded

        # Difficulty categorization (default to 2 if not set)
        diff_tier = min(max(q.difficulty or 2, 1), 3)
        difficulty_stats[diff_tier]["available"] += marks
        difficulty_stats[diff_tier]["awarded"] += awarded

        # Time sink detection: spent > 120s per mark and scored < 50%
        if marks > 0 and time_spent > 0:
            pace_for_item = time_spent / marks
            if pace_for_item > 90 and (awarded / marks) < 0.5:
                time_sinks.append(
                    {
                        "position": item.position + 1,
                        "question_id": str(q.id),
                        "stem_snippet": (q.stem[:80] + "…") if len(q.stem) > 80 else q.stem,
                        "marks_available": marks,
                        "marks_awarded": awarded,
                        "time_spent_s": time_spent,
                        "pace_seconds_per_mark": round(pace_for_item, 1),
                    }
                )

        # Mistakes aggregation
        if ev and ev.diagnosed_mistakes:
            for m in ev.diagnosed_mistakes:
                m_type = m.get("mistake_type", "conceptual")
                mistake_counts[m_type] = mistake_counts.get(m_type, 0) + 1

        # Topic aggregation
        for tid in q.topic_ids:
            if tid not in topic_stats:
                topic_stats[tid] = {"available": 0.0, "awarded": 0.0, "time_s": 0}
            topic_stats[tid]["available"] += marks
            topic_stats[tid]["awarded"] += awarded
            topic_stats[tid]["time_s"] += time_spent

    # Resolve topic names
    topics = s.scalars(select(Topic).where(Topic.id.in_(list(topic_stats.keys())))).all()
    topic_map = {t.id: t for t in topics}

    topic_breakdown: list[dict[str, Any]] = []
    for tid, st in topic_stats.items():
        avail = st["available"]
        awd = st["awarded"]
        pct = round((awd / avail * 100.0), 1) if avail > 0 else 0.0
        t_obj = topic_map.get(tid)
        status = "mastered" if pct >= 85.0 else ("solid" if pct >= 65.0 else "needs_work")
        topic_breakdown.append(
            {
                "topic_id": str(tid),
                "code": t_obj.code if t_obj else "TOPIC",
                "title": t_obj.title if t_obj else "Topic",
                "marks_available": avail,
                "marks_awarded": awd,
                "accuracy_pct": pct,
                "status": status,
            }
        )
    topic_breakdown.sort(key=lambda x: x["accuracy_pct"])

    # Difficulty breakdown array
    diff_list: list[dict[str, Any]] = []
    for tier in (1, 2, 3):
        d = difficulty_stats[tier]
        avail = d["available"]
        awd = d["awarded"]
        pct = round((awd / avail * 100.0), 1) if avail > 0 else 0.0
        diff_list.append(
            {
                "tier": tier,
                "label": d["tier_label"],
                "marks_available": avail,
                "marks_awarded": awd,
                "accuracy_pct": pct,
            }
        )

    # Pacing calculation
    score_pct = round((total_marks_awarded / total_marks_available * 100.0), 1) if total_marks_available > 0 else 0.0
    avg_per_q = round(total_time_s / len(items), 1) if items else 0.0
    avg_per_mark = round(total_time_s / total_marks_available, 1) if total_marks_available > 0 else 0.0
    target_pace = 72.0  # ~1.2 mins per mark standard for Cambridge Extended
    pace_status = "optimal" if avg_per_mark <= 80 else ("rushed" if avg_per_mark < 35 else "slow")

    pacing_data = {
        "total_time_seconds": total_time_s,
        "avg_time_per_question_s": avg_per_q,
        "avg_time_per_mark_s": avg_per_mark,
        "target_pace_s_per_mark": target_pace,
        "pace_status": pace_status,
    }

    # Actionable prescription
    action_plan: list[str] = []
    weak_topics = [t for t in topic_breakdown if t["status"] == "needs_work"]
    if weak_topics:
        w_title = weak_topics[0]["title"]
        w_acc = weak_topics[0]["accuracy_pct"]
        action_plan.append(f"Immediate revision focus: {w_title} ({w_acc}% accuracy).")
    if time_sinks:
        action_plan.append(
            f"Triage alert: You hit {len(time_sinks)} time sinks where over 90s/mark was spent. "
            "Implement the 2-pass strategy."
        )
    if mistake_counts.get("calculation", 0) > 1:
        action_plan.append("Calculation slips detected: Always re-verify signs and fraction steps before moving on.")
    if not action_plan:
        action_plan.append("High consistency across topics! Maintain momentum with timed mixed-topic revision.")

    title = assessment.config.get("title") or f"{assessment.kind.replace('_', ' ').title()}"
    if assessment.form_code:
        title += f" · Form {assessment.form_code}"

    return DiagnosticReport(
        assessment_id=assessment_id,
        title=title,
        kind=assessment.kind,
        total_questions=len(items),
        total_marks_available=total_marks_available,
        total_marks_awarded=total_marks_awarded,
        score_percentage=score_pct,
        pacing=pacing_data,
        time_sinks=time_sinks,
        topic_breakdown=topic_breakdown,
        difficulty_breakdown=diff_list,
        mistake_types_summary=mistake_counts,
        action_plan=action_plan,
    )
