"""Study assessments (PHASE-1 §5) through the real API: forms from reserved items, the test lock (AC-L5),
marks hidden until submission, scoring."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

# Fixture questions written for these tests (not from any copyrighted paper).
SPEC = {"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3", "accept_ranges": []}


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        objective_id, subject_id = s.execute(
            select(LearningObjective.id, Topic.subject_id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(1)
        ).one()

        def item(**overrides: Any) -> str:
            row = QuestionItem(
                **{
                    "tenant_id": w.tenant_id,
                    "subject_id": subject_id,
                    "origin": "school",
                    "source_ref": f"test/{uuid4().hex[:12]}",
                    "stem": "Find the circumference of a circle with radius 2 cm.",
                    "marks": 2,
                    "objective_ids": [objective_id],
                    "answer_spec": SPEC,
                    "mark_scheme": {"text": "M1 for 2 x pi x 2\nA1 12.6", "source": "test_fixture"},
                    "verification_status": "verified",
                    "reserved_for_study": True,
                    **overrides,
                }
            )
            s.add(row)
            s.flush()
            return str(row.id)

        reserved = [item(), item(marks=3)]
        practice = item(reserved_for_study=False)
    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        **vars(w), subject_id=str(subject_id), reserved=reserved, practice=practice, transport=transport, client=client
    )


def marking() -> dict[str, Any]:
    return {
        "awards": [
            {"code": "M1", "awarded": True, "reason": "correct method"},
            {"code": "A1", "awarded": True, "reason": "correct answer"},
        ],
        "marks_awarded": 2,
        "final_answer_correct": True,
        "feedback_summary": "Well done.",
        "what_went_well": "Clear method.",
        "next_step": "Try a question on arc length.",
        "mistakes": [],
        "confidence": 0.9,
    }


def answer(world: SimpleNamespace, headers: dict[str, str], item_id: str, **extra: Any) -> Any:
    body = {
        "question_item_id": item_id,
        "idempotency_key": f"key-{uuid4().hex}",
        "working": "2 x pi x 2",
        "final_answer": "12.6",
        "pre_confidence": 3,
        **extra,
    }
    return world.client.post("/attempts", headers=headers, json=body)


def test_baseline_form_lifecycle(world: SimpleNamespace, auth_headers: Auth) -> None:
    c = world.client
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    form = {"subject_id": world.subject_id, "kind": "baseline", "form_code": "A", "question_item_ids": world.reserved}

    assert c.post("/assessments", headers=student, json=form).status_code == 403  # students never set study forms
    mixed = c.post("/assessments", headers=parent, json={**form, "question_item_ids": [world.practice]})
    assert (mixed.status_code, mixed.json()["error"]["code"]) == (422, "invalid_items")
    created = c.post("/assessments", headers=parent, json=form)
    assert created.status_code == 201, created.text
    test = created.json()
    assert (test["status"], test["total_marks"], test["no_help"]) == ("draft", 5, True)
    assert c.post("/assessments", headers=parent, json=form).json()["error"]["code"] == "duplicate_form"
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert s.scalar(select(AuditLog.id).where(AuditLog.action == "assessment.created")) is not None

    url = f"/assessments/{test['id']}"
    draft = c.get(url, headers=student).json()
    assert all(i["question"] is None for i in draft["items"])  # not visible before the start
    first, second = world.reserved
    early = answer(world, student, first, assessment_id=test["id"])
    assert early.json()["error"]["code"] == "assessment_not_started"

    started = c.post(f"{url}/start", headers=student).json()
    assert started["status"] == "in_progress" and all(i["question"] for i in started["items"])
    assert started["score"] is None  # marks hidden during a study test
    outsider = answer(world, student, world.practice, assessment_id=test["id"])
    assert outsider.json()["error"]["code"] == "item_not_in_assessment"
    assert answer(world, student, world.practice).json()["error"]["code"] == "assessment_in_progress"

    session = c.post("/tutor/sessions", headers=student, json={"subject_id": world.subject_id, "mode": "learn"})
    assert session.status_code == 201, session.text
    help_turn = c.post(f"/tutor/sessions/{session.json()['id']}/help", headers=student, json={})
    assert help_turn.status_code == 200 and "can't help" in help_turn.text  # AC-L5
    assert world.transport.requests == []  # the lock needs no LLM call

    attempt = answer(world, student, first, assessment_id=test["id"])
    assert attempt.status_code == 201, attempt.text
    assert answer(world, student, first, assessment_id=test["id"]).json()["error"]["code"] == "already_answered"
    blocked = c.post(f"/attempts/{attempt.json()['id']}/evaluate", headers=student)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "assessment_not_submitted")

    submitted = c.post(f"{url}/submit", headers=student).json()
    assert submitted["status"] == "submitted"
    assert submitted["score"] == {
        "awarded": 0,
        "available": 5,
        "answered": 1,
        "unmarked": 1,
        "pending_review": 0,
        "final": False,
    }
    assert answer(world, student, second, assessment_id=test["id"]).json()["error"]["code"] == "assessment_closed"

    world.transport.reply(marking())
    marked = c.post(f"/attempts/{attempt.json()['id']}/evaluate", headers=student).json()
    assert marked["status"] == "final"
    final = c.get(url, headers=parent).json()
    assert final["score"] == {
        "awarded": 2,
        "available": 5,
        "answered": 1,
        "unmarked": 0,
        "pending_review": 0,
        "final": True,
    }
    assert [a["id"] for a in c.get("/assessments", headers=student).json()] == [test["id"]]
    assert answer(world, student, world.practice).status_code == 201  # the lock ends with the submission
