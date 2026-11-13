"""Unit tests for digital notebooks and assessment performance analytics."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.assessment import analytics
from app.modules.assessment.schemas import (
    AssessmentReportOut,
    DifficultyBreakdownItem,
    NotebookCreate,
    NotebookItemOut,
    NotebookOut,
    PacingSummary,
    TimeSinkItem,
    TopicBreakdownItem,
)


def test_no_grade_is_projected_from_invented_boundaries() -> None:
    # Cambridge sets boundaries per component per series; a fixed percentage table would be invented (PRINCIPLES 9).
    assert not hasattr(analytics, "compute_projected_grade")
    assert "projected_grade" not in AssessmentReportOut.model_fields


def test_notebook_schemas_validate() -> None:
    create = NotebookCreate(
        title="Trig & Angle Traps",
        description="Questions with bearings or 3D angles",
        icon="🪤",
        color="amber",
    )
    assert create.title == "Trig & Angle Traps"
    assert create.icon == "🪤"

    nb_id = uuid4()
    student_id = uuid4()
    now = datetime.now(UTC)
    out = NotebookOut(
        id=nb_id,
        student_id=student_id,
        title=create.title,
        description=create.description,
        icon=create.icon,
        color=create.color,
        subject_id=None,
        item_count=5,
        created_at=now,
        updated_at=now,
    )
    assert out.id == nb_id
    assert out.item_count == 5


def test_notebook_item_schema_validate() -> None:
    now = datetime.now(UTC)
    item = NotebookItemOut(
        id=uuid4(),
        notebook_id=uuid4(),
        question_item_id=uuid4(),
        student_notes="Watch out for negative cosine in quadrant 2",
        created_at=now,
        question=None,
    )
    assert item.student_notes is not None
    assert "negative cosine" in item.student_notes


def test_assessment_report_schema_validate() -> None:
    report = AssessmentReportOut(
        assessment_id=uuid4(),
        title="Mock Exam May 2024 Paper 4",
        kind="exam_style",
        total_questions=12,
        total_marks_available=80.0,
        total_marks_awarded=68.0,
        score_percentage=85.0,
        pacing=PacingSummary(
            total_time_seconds=4800,
            avg_time_per_question_s=400.0,
            avg_time_per_mark_s=60.0,
            target_pace_s_per_mark=72.0,
            pace_status="optimal",
        ),
        time_sinks=[
            TimeSinkItem(
                position=4,
                question_id=str(uuid4()),
                stem_snippet="Calculate the angle between planes ABCD and EFGH...",
                marks_available=4.0,
                marks_awarded=1.0,
                time_spent_s=420,
                pace_seconds_per_mark=105.0,
            )
        ],
        topic_breakdown=[
            TopicBreakdownItem(
                topic_id=str(uuid4()),
                code="E6.2",
                title="Coordinate Geometry",
                marks_available=12.0,
                marks_awarded=12.0,
                accuracy_pct=100.0,
                status="mastered",
            ),
            TopicBreakdownItem(
                topic_id=str(uuid4()),
                code="E3.4",
                title="Mensuration",
                marks_available=16.0,
                marks_awarded=10.0,
                accuracy_pct=62.5,
                status="needs_work",
            ),
        ],
        difficulty_breakdown=[
            DifficultyBreakdownItem(
                tier=1,
                label="Foundation / Recall",
                marks_available=20.0,
                marks_awarded=20.0,
                accuracy_pct=100.0,
            ),
            DifficultyBreakdownItem(
                tier=2,
                label="Application / Multi-Step",
                marks_available=40.0,
                marks_awarded=36.0,
                accuracy_pct=90.0,
            ),
            DifficultyBreakdownItem(
                tier=3,
                label="Complex / Problem-Solving",
                marks_available=20.0,
                marks_awarded=12.0,
                accuracy_pct=60.0,
            ),
        ],
        mistake_types_summary={"calculation": 2, "conceptual": 1},
        action_plan=["Focus on Mensuration: 62.5% accuracy."],
    )
    assert report.pacing.pace_status == "optimal"
    assert len(report.time_sinks) == 1
    assert report.time_sinks[0].position == 4
