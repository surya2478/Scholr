"""Validation-study tooling through the real API: matched pairs, study forms, results, crossover (PHASE-1 §5)."""

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
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

# Fixture questions written for these tests (not from any copyrighted paper).
SPEC = {"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3", "accept_ranges": []}
MARKING = {
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


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        rows = s.execute(
            select(LearningObjective.id, Topic.subject_id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(3)
        ).all()
        subject_id = rows[0][1]
        app_objectives, control_objective = [rows[0][0], rows[1][0]], rows[2][0]

        def item(objective_id: Any) -> str:
            row = QuestionItem(
                tenant_id=w.tenant_id,
                subject_id=subject_id,
                origin="school",
                source_ref=f"test/{uuid4().hex[:12]}",
                stem="Find the circumference of a circle with radius 2 cm.",
                marks=2,
                objective_ids=[objective_id],
                answer_spec=SPEC,
                mark_scheme={"text": "M1 for 2 x pi x 2\nA1 12.6", "source": "test_fixture"},
                verification_status="verified",
                reserved_for_study=True,
            )
            s.add(row)
            s.flush()
            return str(row.id)

        forms = {kind: [item(app_objectives[0]), item(control_objective)] for kind in ("baseline", "post")}
    gateway, transport, _ = scripted_gateway()
    return SimpleNamespace(
        **vars(w),
        subject_id=str(subject_id),
        app_objectives=[str(o) for o in app_objectives],
        control_objective=str(control_objective),
        forms=forms,
        transport=transport,
        client=TestClient(create_app(session_factory=w.factory, gateway=gateway)),
    )


def sit_form(
    world: SimpleNamespace, student: dict[str, str], parent: dict[str, str], kind: str, code: str, answer_first: bool
) -> None:
    c = world.client
    body = {"subject_id": world.subject_id, "kind": kind, "form_code": code, "question_item_ids": world.forms[kind]}
    test = c.post("/assessments", headers=parent, json=body).json()
    c.post(f"/assessments/{test['id']}/start", headers=student)
    attempt_id = None
    if answer_first:
        attempt = c.post(
            "/attempts",
            headers=student,
            json={
                "question_item_id": world.forms[kind][0],
                "idempotency_key": f"key-{uuid4().hex}",
                "working": "2 x pi x 2",
                "final_answer": "12.6",
                "assessment_id": test["id"],
            },
        )
        assert attempt.status_code == 201, attempt.text
        attempt_id = attempt.json()["id"]
    assert c.post(f"/assessments/{test['id']}/submit", headers=student).json()["status"] == "submitted"
    if attempt_id:
        world.transport.reply(MARKING)
        assert c.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()["status"] == "final"


def test_pairs_results_and_crossover(world: SimpleNamespace, auth_headers: Auth) -> None:
    c = world.client
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    pair = {
        "subject_id": world.subject_id,
        "pair_code": "P1",
        "app_objective_ids": world.app_objectives,
        "control_objective_ids": [world.control_objective],
        "assignment_method": "coin flip recorded by parent",
    }
    assert c.post("/studies/assignments", headers=student, json=pair).status_code == 403
    overlap = c.post(
        "/studies/assignments", headers=parent, json={**pair, "control_objective_ids": world.app_objectives[:1]}
    )
    assert overlap.json()["error"]["code"] == "arms_overlap"
    created = c.post("/studies/assignments", headers=parent, json=pair)
    assert created.status_code == 201, created.text
    assert [a["arm"] for a in created.json()] == ["app", "control"]
    assert c.post("/studies/assignments", headers=parent, json=pair).json()["error"]["code"] == "duplicate_pair"

    url = f"/studies/{world.subject_id}/results"
    assert c.get(url, headers=parent).json()["decision"] == "pending"
    assert c.get(url, headers=student).status_code == 403

    sit_form(world, student, parent, "baseline", "A", answer_first=False)  # nothing answered: 0 on both topics
    sit_form(world, student, parent, "post", "B", answer_first=True)  # app topic question answered correctly

    results = c.get(url, headers=parent).json()
    assert [f["kind"] for f in results["forms"]] == ["baseline", "post"]
    app, control = results["arms"]
    assert (app["arm"], app["gain"], app["post"]["awarded"], app["eligible"]) == ("app", 1.0, 2, False)
    assert (control["gain"], control["post"]["awarded"]) == (0.0, 0)
    assert results["gain_difference"] == 1.0 and results["decision"] == "iterate"
    assert "engagement_below_3_sessions_per_week" in results["reasons"]
    assert "topic_baseline_outside_20_70" in results["reasons"]

    early = c.post(f"/studies/{world.subject_id}/crossover", headers=parent)
    assert (early.status_code, early.json()["error"]["code"]) == (409, "retention_not_done")
