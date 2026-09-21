"""Goals through the real API (AC-G1): agreed with the student, and measured from evidence, never claimed."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
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


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        subject_id = s.scalar(select(Subject.id).where(Subject.code == "igcse-maths"))
        objectives = list(
            s.scalars(
                select(LearningObjective.id)
                .join(Topic, Topic.id == LearningObjective.topic_id)
                .where(Topic.subject_id == subject_id)
                .order_by(LearningObjective.code)
                .limit(4)
            )
        )
    client = TestClient(create_app(session_factory=w.factory))
    return SimpleNamespace(**vars(w), client=client, subject_id=subject_id, objectives=objectives)


def secure(world: SimpleNamespace, objective_id, count: int = 4) -> None:
    """Enough good independent answers on one objective to reach competent."""
    now = datetime.now(UTC)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        new = [
            events.append(
                s,
                tenant_id=world.tenant_id,
                student_id=world.student_id,
                event_type="attempt_evaluated",
                occurred_at=now - timedelta(days=n),
                subject_id=world.subject_id,
                objective_ids=[objective_id],
                payload={
                    "attempt_id": uuid4(),
                    "evaluation_id": uuid4(),
                    "marks_awarded": 3,
                    "marks_available": 3,
                    "help_level": 0,
                    "evaluation_confidence": 0.95,
                    "status": "final",
                    "exam_style": True,
                },
            )
            for n in range(count)
        ]
        mastery.project(s, new, tenant_id=world.tenant_id, now=now)


def goal_body(world: SimpleNamespace, **kw: object) -> dict[str, object]:
    return {
        "statement": "Get eight Maths topics secure before the mock",
        "measure": "topics_secure",
        "target_value": 2,
        "subject_id": str(world.subject_id),
        "target_date": (date.today() + timedelta(days=60)).isoformat(),
        **kw,
    }


def test_a_goal_the_student_sets_is_active_at_once(world: SimpleNamespace, auth_headers: Auth) -> None:
    created = world.client.post("/goals", headers=auth_headers("test|student"), json=goal_body(world))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "active" and body["agreed"] is True
    assert body["proposed_by_role"] == "student"
    assert body["baseline"] == 0.0, "where it stood when she set it"
    assert body["direction"] == "rise" and body["share"] == 0.0


def test_a_goal_a_parent_proposes_waits_for_her(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-G1
    created = world.client.post(
        f"/goals?student_id={world.student_id}", headers=auth_headers("test|parent"), json=goal_body(world)
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "proposed"
    assert created.json()["agreed"] is False


def test_a_parent_cannot_agree_on_her_behalf(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-G1
    goal = world.client.post(
        f"/goals?student_id={world.student_id}", headers=auth_headers("test|parent"), json=goal_body(world)
    ).json()
    refused = world.client.post(f"/goals/{goal['id']}/agree", headers=auth_headers("test|parent"))
    assert refused.status_code == 403

    agreed = world.client.post(f"/goals/{goal['id']}/agree", headers=auth_headers("test|student"))
    assert agreed.status_code == 200
    assert agreed.json()["status"] == "active" and agreed.json()["agreed"] is True


def test_progress_comes_from_evidence_not_from_saying_so(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    world.client.post("/goals", headers=student, json=goal_body(world))

    before = world.client.get("/goals", headers=student).json()[0]
    assert before["current"] == 0.0 and before["status"] == "active"

    secure(world, world.objectives[0])
    secure(world, world.objectives[1])

    after = world.client.get("/goals", headers=student).json()[0]
    assert after["current"] == 2.0, "two objectives reached competent, so the goal moved"
    assert after["share"] == 1.0
    assert after["status"] == "achieved", "settled from the evidence, with nobody claiming it"


def test_a_goal_that_asks_for_nothing_is_refused(world: SimpleNamespace, auth_headers: Auth) -> None:
    refused = world.client.post("/goals", headers=auth_headers("test|student"), json=goal_body(world, target_value=0))
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "target_not_reachable"


def test_a_target_date_in_the_past_is_refused(world: SimpleNamespace, auth_headers: Auth) -> None:
    refused = world.client.post(
        "/goals",
        headers=auth_headers("test|student"),
        json=goal_body(world, target_date=(date.today() - timedelta(days=1)).isoformat()),
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "target_date_past"


def test_a_subject_measure_needs_a_subject(world: SimpleNamespace, auth_headers: Auth) -> None:
    refused = world.client.post("/goals", headers=auth_headers("test|student"), json=goal_body(world, subject_id=None))
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "subject_required"


def test_either_of_them_may_let_a_goal_go(world: SimpleNamespace, auth_headers: Auth) -> None:
    goal = world.client.post("/goals", headers=auth_headers("test|student"), json=goal_body(world)).json()
    dropped = world.client.post(
        f"/goals/{goal['id']}/drop?student_id={world.student_id}", headers=auth_headers("test|parent")
    )
    assert dropped.status_code == 200 and dropped.json()["status"] == "dropped"


def test_both_of_them_read_the_same_goals(world: SimpleNamespace, auth_headers: Auth) -> None:
    world.client.post("/goals", headers=auth_headers("test|student"), json=goal_body(world))
    hers = world.client.get("/goals", headers=auth_headers("test|student")).json()
    theirs = world.client.get(f"/goals?student_id={world.student_id}", headers=auth_headers("test|parent")).json()
    assert [g["id"] for g in hers] == [g["id"] for g in theirs]
