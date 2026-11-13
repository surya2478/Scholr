"""Schedule data endpoints and My Day through the real API: capacity, signals from events, control-arm exclusion,
item status events."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.core.ids import uuid7
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events import service as events
from app.modules.events.models import LearningEvent
from app.modules.mastery import service as mastery
from app.modules.studies.models import StudyAssignment

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        rows = s.execute(
            select(LearningObjective.id, Topic.id, Topic.subject_id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(3)
        ).all()
    client = TestClient(create_app(session_factory=w.factory))
    return SimpleNamespace(
        **vars(w), objectives=[r[0] for r in rows], topic_id=rows[0][1], subject_id=rows[0][2], client=client
    )


def weak_evidence(world: SimpleNamespace, objective_id) -> None:  # noqa: ANN001
    now = datetime.now(UTC)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        new = [
            events.append(
                s,
                tenant_id=world.tenant_id,
                student_id=world.student_id,
                event_type="attempt_evaluated",
                occurred_at=now - timedelta(hours=h),
                objective_ids=[objective_id],
                payload={
                    "attempt_id": uuid4(),
                    "evaluation_id": uuid4(),
                    "marks_awarded": 1,
                    "marks_available": 3,
                    "help_level": 2,
                    "evaluation_confidence": 0.9,
                    "status": "final",
                },
            )
            for h in (1, 2, 3)
        ]
        mastery.project(s, new, tenant_id=world.tenant_id, now=now)


def test_schedule_endpoints_and_my_day(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    c = world.client
    week = c.put(f"/students/{world.student_id}/availability", headers=parent, json={"minutes": [90] * 7}).json()
    assert week["minutes"] == [90] * 7
    bad = c.post(
        "/commitments",
        headers=parent,
        json={"kind": "iit_class", "title": "IIT", "rrule": "FREQ=MONTHLY", "duration_min": 60},
    )
    assert bad.status_code == 422
    commitment = c.post(
        "/commitments",
        headers=parent,
        json={
            "kind": "iit_class",
            "title": "IIT",
            "rrule": "freq=weekly;byday=MO,TU,WE,TH,FR,SA,SU",
            "duration_min": 30,
        },
    )
    assert commitment.status_code == 201 and commitment.json()["rrule"].startswith("FREQ=WEEKLY")
    today = datetime.now(UTC)
    teaching = c.post(
        "/teaching-plan",
        headers=student,
        json={
            "subject_id": str(world.subject_id),
            "term": "Term 1",
            "label": "Number",
            "starts_on": str((today - timedelta(days=7)).date()),
            "ends_on": str((today + timedelta(days=7)).date()),
            "topic_ids": [str(world.topic_id)],
        },
    )
    assert teaching.status_code == 201
    upcoming = c.post(
        "/upcoming-assessments",
        headers=parent,
        json={
            "subject_id": str(world.subject_id),
            "title": "Unit test",
            "due_at": (today + timedelta(days=5)).isoformat(),
            "objective_ids": [str(world.objectives[1])],
        },
    )
    assert upcoming.status_code == 201
    weak_evidence(world, world.objectives[2])
    with world.factory() as s, s.begin():  # the first objective is the control arm of the validation study
        set_rls_context(s, user_id=None, role="system")
        s.add(
            StudyAssignment(
                tenant_id=world.tenant_id,
                student_id=world.student_id,
                subject_id=world.subject_id,
                pair_code="P1",
                arm="control",
                objective_ids=[world.objectives[0]],
                assignment_method="test",
                assigned_at=today,
            )
        )

    plan = c.get("/plan/today", headers=student).json()
    capacity = 90 - 30 - 9  # availability - commitment - 15% buffer (every day equal: Monday is the lighter day)
    assert plan["capacity_minutes"] in (capacity, int(capacity * 0.6))
    assert plan["planned_minutes"] <= plan["capacity_minutes"]  # AC-P1
    planned = {item["objective_id"] for item in plan["items"]} | {d["objective_code"] for d in plan["dropped"]}
    assert str(world.objectives[0]) not in planned  # AC-P2
    kinds = [item["kind"] for item in plan["items"]]
    assert kinds[0] == "assessment" and all(item["reason"] for item in plan["items"])
    assert c.get("/plan/today", headers=parent).json()["id"] == plan["id"]  # same plan, parent view

    first = plan["items"][0]["id"]
    assert c.patch(f"/plan/items/{first}", headers=parent, json={"status": "completed"}).status_code == 403
    done = c.patch(f"/plan/items/{first}", headers=student, json={"status": "completed"}).json()
    assert done["items"][0]["status"] == "completed"
    assert c.patch(f"/plan/items/{first}", headers=student, json={"status": "skipped"}).status_code == 409
    regenerated = c.post("/plan/regenerate", headers=student).json()
    assert regenerated["items"][0]["status"] == "completed"  # finished work survives regeneration
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert "plan_item_completed" in set(s.scalars(select(LearningEvent.type)))

    result = c.post(
        "/school-results",
        headers=parent,
        json={
            "subject_id": str(world.subject_id),
            "title": "Quiz",
            "assessed_on": str(today.date()),
            "score": 7,
            "max_score": 10,
        },
    )
    assert result.status_code == 201


def test_a_day_with_no_study_time_never_also_says_the_day_is_full(world: SimpleNamespace, auth_headers: Auth) -> None:
    """Her Monday, 26 Oct 2026: one IIT class in the evening, no study window — and My Day said both "today is
    full, so optional practice was left out" and "no study time is planned for today. Enjoy the break!"."""
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    c = world.client
    assert c.put(f"/students/{world.student_id}/availability", headers=parent, json={"minutes": [0] * 7}).json()
    # Core work the planner wants to set, with nowhere to put it: that is what made it call the day "full".
    assert (
        c.post(
            "/upcoming-assessments",
            headers=parent,
            json={
                "subject_id": str(world.subject_id),
                "title": "Unit test",
                "due_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
                "objective_ids": [str(world.objectives[1])],
            },
        ).status_code
        == 201
    )

    plan = c.post("/plan/regenerate", headers=student).json()
    assert plan["capacity_minutes"] == 0 and plan["items"] == []
    assert plan["dropped"], "the day had core work it could not place — the old notice called that 'full'"
    assert len(plan["notices"]) == 1
    assert "No study time is planned" in plan["notices"][0]
    assert not any("optional practice" in n for n in plan["notices"])


def test_coming_up_leaves_out_a_test_that_has_passed(world: SimpleNamespace, auth_headers: Auth) -> None:
    """Her home page, 13 Nov 2026: "Coming up: Sociology pre-mock", a mock that was due on 5 Nov."""
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    c = world.client
    now = datetime.now(UTC)
    for title, due in (("Past mock", now - timedelta(days=8)), ("Next test", now + timedelta(days=3))):
        body = {"subject_id": str(world.subject_id), "title": title, "due_at": due.isoformat(), "objective_ids": []}
        assert c.post("/upcoming-assessments", headers=parent, json=body).status_code == 201

    coming = c.get("/upcoming-assessments?upcoming_only=true", headers=student).json()
    assert [u["title"] for u in coming] == ["Next test"]
    # The parent's schedule still lists both, so the past one can be cleared.
    assert {u["title"] for u in c.get("/upcoming-assessments", headers=parent).json()} >= {"Past mock", "Next test"}


def test_a_topic_with_questions_is_done_only_once_she_has_answered_one(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    """Improvement 1: reading a topic is not finishing it. Done waits for an answer that day; Skip never does."""
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    c = world.client
    assert c.put(f"/students/{world.student_id}/availability", headers=parent, json={"minutes": [120] * 7}).json()
    for objective in world.objectives[1:]:
        weak_evidence(world, objective)
    plan = c.post("/plan/regenerate", headers=student).json()
    item = next(i for i in plan["items"] if i["objective_id"])
    objective = item["objective_id"]
    assert item["needs_answer"] is False  # no questions on the topic yet: nothing to answer, Done as before

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        s.add(
            QuestionItem(
                id=uuid7(), tenant_id=world.tenant_id, subject_id=world.subject_id, origin="past_paper",
                source_ref="0580/21/MJ25/Q1", stem="Fixture stem", marks=1, objective_ids=[objective],
                verification_status="verified", mark_scheme={"answer": "1"},
            )
        )  # fmt: skip
    plan = c.get("/plan/today", headers=student).json()
    item = next(i for i in plan["items"] if i["id"] == item["id"])
    assert item["needs_answer"] is True
    refused = c.patch(f"/plan/items/{item['id']}", headers=student, json={"status": "completed"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "answer_first"

    with world.factory() as s, s.begin():  # an answer from yesterday does not count for today
        set_rls_context(s, user_id=None, role="system")
        events.append(
            s, tenant_id=world.tenant_id, student_id=world.student_id, event_type="attempt_submitted",
            occurred_at=datetime.now(UTC) - timedelta(days=2), objective_ids=[UUID(objective)],
            subject_id=world.subject_id,
            payload={"attempt_id": uuid4(), "question_item_id": uuid4(), "assessment_id": None, "session_id": None},
        )  # fmt: skip
    assert c.patch(f"/plan/items/{item['id']}", headers=student, json={"status": "completed"}).status_code == 409

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        events.append(
            s, tenant_id=world.tenant_id, student_id=world.student_id, event_type="attempt_submitted",
            occurred_at=datetime.now(UTC), objective_ids=[UUID(objective)], subject_id=world.subject_id,
            payload={"attempt_id": uuid4(), "question_item_id": uuid4(), "assessment_id": None, "session_id": None},
        )  # fmt: skip
    done = c.patch(f"/plan/items/{item['id']}", headers=student, json={"status": "completed"}).json()
    assert next(i for i in done["items"] if i["id"] == item["id"])["status"] == "completed"


def test_skip_never_waits_for_an_answer(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    c = world.client
    assert c.put(f"/students/{world.student_id}/availability", headers=parent, json={"minutes": [120] * 7}).json()
    for objective in world.objectives[1:]:
        weak_evidence(world, objective)
    item = next(i for i in c.post("/plan/regenerate", headers=student).json()["items"] if i["objective_id"])
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        s.add(
            QuestionItem(
                id=uuid7(), tenant_id=world.tenant_id, subject_id=world.subject_id, origin="past_paper",
                source_ref="0580/21/MJ25/Q2", stem="Fixture stem", marks=1, objective_ids=[UUID(item["objective_id"])],
                verification_status="verified", mark_scheme={"answer": "1"},
            )
        )  # fmt: skip
    assert c.patch(f"/plan/items/{item['id']}", headers=student, json={"status": "skipped"}).status_code == 200
