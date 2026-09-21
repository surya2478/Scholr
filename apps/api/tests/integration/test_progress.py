"""Progress summary and guardian overview through the real API, with RLS and scope checks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events import service as events
from app.modules.mastery import service as mastery

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


def test_summary_and_guardian_overview(household_world: SimpleNamespace, auth_headers: Auth) -> None:
    w = household_world
    now = datetime.now(UTC)
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        objective_id, subject_id = s.execute(
            select(LearningObjective.id, Subject.id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(1)
        ).one()
        new = [
            events.append(
                s,
                tenant_id=w.tenant_id,
                student_id=w.student_id,
                event_type="attempt_evaluated",
                occurred_at=now - timedelta(days=days, minutes=5),
                objective_ids=[objective_id],
                payload={
                    "attempt_id": uuid4(),
                    "evaluation_id": uuid4(),
                    "marks_awarded": 3,
                    "marks_available": 3,
                    "help_level": 0,
                    "evaluation_confidence": 0.95,
                    "status": "final",
                },
            )
            for days in (0, 1, 2, 3)
        ]
        old = events.append(  # outside the week: counts for mastery, not for this week's stats
            s,
            tenant_id=w.tenant_id,
            student_id=w.student_id,
            event_type="attempt_submitted",
            occurred_at=now - timedelta(days=20),
            objective_ids=[objective_id],
            payload={"attempt_id": uuid4(), "question_item_id": uuid4()},
        )
        mastery.project(s, [*new, old], tenant_id=w.tenant_id, now=now)

    client = TestClient(create_app(session_factory=w.factory))
    student, parent = auth_headers("test|student"), auth_headers("test|parent")

    summary = client.get("/progress/summary", headers=student)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    maths = next(p for p in body["subjects"] if p["subject_id"] == str(subject_id))
    assert maths["objectives_total"] > 1
    assert sum(maths["level_counts"].values()) == maths["objectives_total"]
    assert body["week"]["attempts_evaluated"] == 4 and 1 <= body["week"]["active_days"] <= 4

    assert client.get(f"/guardian/students/{w.student_id}/overview", headers=student).status_code == 403
    overview = client.get(f"/guardian/students/{w.student_id}/overview", headers=parent)
    assert overview.status_code == 200, overview.text
    data = overview.json()
    assert data["student_name"] and "progress" in data["scopes"]
    assert data["summary"]["week"]["attempts_evaluated"] == 4
    assert data["safety"] == {
        "open_total": 0,
        "open_by_severity": {"low": 0, "medium": 0, "high": 0},
        "latest_open_at": None,
    }
    assert data["evaluations_needing_review"] == 0 and data["upcoming_assessments"] == []
    assert client.get(f"/guardian/students/{uuid4()}/overview", headers=parent).status_code == 403
