"""Guardian monthly summary through the real API: aggregation from stored events, scope and month checks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events import service as events

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


def test_guardian_monthly_summary(household_world: SimpleNamespace, api_client: TestClient, auth_headers: Auth) -> None:
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
        common = {"tenant_id": w.tenant_id, "student_id": w.student_id, "subject_id": subject_id}
        events.append(
            s,
            event_type="attempt_evaluated",
            occurred_at=now - timedelta(minutes=3),
            payload={
                "attempt_id": uuid4(),
                "evaluation_id": uuid4(),
                "marks_awarded": 2,
                "marks_available": 3,
                "help_level": 0,
                "evaluation_confidence": 0.9,
                "status": "final",
            },
            objective_ids=[objective_id],
            **common,
        )
        events.append(
            s,
            event_type="session_ended",
            occurred_at=now - timedelta(minutes=1),
            payload={"session_id": uuid4(), "active_minutes": 25},
            objective_ids=[],
            **common,
        )

    parent, student = auth_headers("test|parent"), auth_headers("test|student")
    url = f"/guardian/students/{w.student_id}/monthly"
    resp = api_client.get(url, headers=parent)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    [maths] = body["subjects"]
    assert (maths["answers_marked"], maths["accuracy"], maths["study_minutes"], maths["sessions"]) == (1, 0.667, 25, 1)
    assert body["next_month"] is None and body["focus"] is not None and body["totals"]["active_days"] == 1

    previous = api_client.get(url, headers=parent, params={"month": body["previous_month"]}).json()
    assert previous["totals"]["answers_marked"] == 0 and previous["focus"] is None
    assert previous["next_month"] == body["month"]

    assert api_client.get(url, headers=student).status_code == 403
    assert api_client.get(url, headers=parent, params={"month": "2999-01"}).status_code == 422
    assert api_client.get(url, headers=parent, params={"month": "2026-13"}).status_code == 422


def test_guardian_trends(household_world: SimpleNamespace, api_client: TestClient, auth_headers: Auth) -> None:
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
        common = {"tenant_id": w.tenant_id, "student_id": w.student_id, "subject_id": subject_id}
        for help_level in (0, 3):
            events.append(
                s,
                event_type="attempt_evaluated",
                occurred_at=now - timedelta(minutes=5),
                payload={
                    "attempt_id": uuid4(),
                    "evaluation_id": uuid4(),
                    "marks_awarded": 2,
                    "marks_available": 3,
                    "help_level": help_level,
                    "evaluation_confidence": 0.9,
                    "status": "final",
                },
                objective_ids=[objective_id],
                **common,
            )
        events.append(
            s,
            event_type="session_ended",
            occurred_at=now - timedelta(minutes=2),
            payload={"session_id": uuid4(), "active_minutes": 40},
            objective_ids=[],
            **common,
        )

    parent, student = auth_headers("test|parent"), auth_headers("test|student")
    url = f"/guardian/students/{w.student_id}/trends"
    resp = api_client.get(url, headers=parent, params={"weeks": 4})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["weeks"]) == 4 and len(body["days"]) == 7
    current = body["weeks"][-1]
    assert (current["answers_marked"], current["without_help"], current["with_hints"]) == (2, 1, 1)
    assert current["independent_share"] == 0.5 and current["topics_secure"] is not None
    assert sum(d["study_minutes"] for d in body["days"]) == 40
    assert [s["subject_name"] for s in body["subjects"]] == ["Mathematics"]

    assert api_client.get(url, headers=student).status_code == 403
    assert api_client.get(url, headers=parent, params={"weeks": 99}).status_code == 422
