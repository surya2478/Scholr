"""Unit tests for the Metacognitive Error Autopsy feature."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.rbac import Principal
from app.modules.evaluation.models import Evaluation
from app.modules.evaluation.schemas import AutopsyEntryOut, AutopsyIn, FeedbackOut
from app.modules.evaluation.service import record_autopsy


def test_autopsy_schemas_validate() -> None:
    body = AutopsyIn(category="conceptual", takeaway="Always factor out before cancelling terms.")
    assert body.category == "conceptual"
    assert "factor" in body.takeaway

    entry = AutopsyEntryOut(
        evaluation_id=uuid4(),
        attempt_id=uuid4(),
        subject_id=uuid4(),
        objective_code="1.2",
        stem="Simplify $\\frac{4x+12}{4x}$",
        category="conceptual",
        takeaway="Factorisation first",
        marks_awarded=0.0,
        marks_available=2.0,
        recorded_at=datetime.now(UTC),
    )
    assert entry.marks_awarded == 0.0
    assert entry.objective_code == "1.2"


def test_feedback_out_includes_autopsy() -> None:
    fb = FeedbackOut(
        summary="Good attempt",
        what_went_well="Copied correctly",
        next_step="Review factorisation",
        autopsy={"category": "calculation", "takeaway": "Sign error on line 2"},
    )
    dumped = fb.model_dump()
    assert dumped["autopsy"] is not None
    assert dumped["autopsy"]["category"] == "calculation"


def test_record_autopsy_updates_evaluation_feedback() -> None:
    student_id = uuid4()
    eval_id = uuid4()
    principal = Principal(
        user_id=student_id,
        tenant_id=uuid4(),
        role="student",
        display_name="Student",
        mfa=False,
        student_id=student_id,
    )

    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    ev_row = Evaluation(
        id=eval_id,
        attempt_id=uuid4(),
        tenant_id=principal.tenant_id,
        student_id=student_id,
        pipeline="structured_math",
        pipeline_version="v1",
        marks_awarded=1.0,
        marks_available=2.0,
        status="final",
        confidence=1.0,
        feedback={"summary": "Missed accuracy mark", "next_step": "Check signs"},
        diagnosed_mistakes=[],
        created_at=now,
    )

    session = MagicMock()
    session.get.return_value = ev_row

    body = AutopsyIn(category="calculation", takeaway="Remember that -2 * -4 = +8")

    result = record_autopsy(session, principal, eval_id, body, now=now)

    assert result.feedback.autopsy is not None
    assert result.feedback.autopsy["category"] == "calculation"
    assert result.feedback.autopsy["takeaway"] == "Remember that -2 * -4 = +8"
    assert session.flush.called
