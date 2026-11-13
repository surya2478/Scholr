"""Sociology feedback the same day, without a mark (improvement 2, AC-E6).

The essay marker is not calibrated (U3), so every Sociology mark waits for a parent. She still gets feedback at
once: what her answer did and what would earn more, from the mark-scheme marking itself — never a number, a level
or a summary that states one, and nothing mastery reads. The LLM is a scripted transport (tests/fixtures/llm.py);
the pipeline, the agreement rules and the projections are real. The question below is fixture text written for
this test.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import API_ROOT
from app.core.db import set_rls_context
from app.core.ids import uuid7
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.seed.curriculum import load_file, seed_curriculum
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

SOCIOLOGY = API_ROOT.parents[1] / "content" / "curriculum" / "igcse-sociology-0495.yaml"


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_curriculum(s, load_file(SOCIOLOGY))
        subject_id = s.scalar(select(Subject.id).where(Subject.code == "igcse-sociology"))
        objective_id = s.scalar(
            select(LearningObjective.id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .where(Topic.subject_id == subject_id)
            .order_by(LearningObjective.code)
        )
        item_id = uuid7()
        s.add(
            QuestionItem(
                id=item_id,
                tenant_id=w.tenant_id,
                subject_id=subject_id,
                origin="past_paper",
                source_ref="test/0495/fixture/Q1(b)",
                stem="Describe two examples of formal education.",
                marks=4,
                command_word="describe",
                objective_ids=[objective_id],
                verification_status="verified",
                mark_scheme={"text": "1 mark per example identified, 1 mark per development (2x2)."},
            )
        )
    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(**vars(w), client=client, transport=transport, item=item_id, objective_id=objective_id)


def marker(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "marks_awarded": 3,
        "level": None,
        "ao_marks": {"AO1": 2, "AO2": 1, "AO3": 0},
        "credited_points": ["lessons in school classrooms", "taught by trained teachers"],
        "missing": ["Develop the second example: say who sets the curriculum."],
        "feedback_summary": "A clear answer earning 3 of the 4 marks.",
        "what_went_well": "Both examples are clearly formal education.",
        "next_step": "Add one sentence that develops your second example.",
        "mistakes": [],
        "confidence": 0.9,
    }
    values.update(overrides)
    return values


def answer(world: SimpleNamespace, student: dict[str, str]) -> dict[str, Any]:
    attempt = world.client.post(
        "/attempts",
        headers=student,
        json={
            "question_item_id": str(world.item),
            "idempotency_key": f"key-{uuid4().hex}",
            "working": "Lessons in school classrooms, taught by trained teachers. Homeschooling with a tutor.",
        },
    )
    assert attempt.status_code == 201, attempt.text
    world.transport.reply(marker())
    world.transport.reply(marker())
    return world.client.post(f"/attempts/{attempt.json()['id']}/evaluate", headers=student).json()


def test_she_gets_feedback_at_once_but_no_mark_until_a_parent_checks(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    evaluation = answer(world, student)

    assert (evaluation["status"], evaluation["provisional"]) == ("needs_review", True)  # not calibrated (U3)
    assert evaluation["marks_awarded"] is None
    assert evaluation["feedback"]["summary"] == ""  # the model's summary states the mark
    pending = evaluation["pending"]
    assert pending["points_made"] == ["lessons in school classrooms", "taught by trained teachers"]
    assert pending["points_missed"] == ["Develop the second example: say who sets the curriculum."]
    assert "parent" in pending["who"] and pending["waiting_since"]
    assert evaluation["feedback"]["next_step"].startswith("Add one sentence")

    # Nothing mastery reads, nothing in the mistake bank, and no number anywhere else she looks.
    assert world.client.get(f"/mastery/{world.objective_id}/evidence", headers=student).json() == []
    topic = world.client.get(f"/learn/objectives/{world.objective_id}", headers=student).json()
    [card] = [c for c in topic["check_yourself"] + topic["exam_questions"] if c["id"] == str(world.item)]
    assert (card["last_status"], card["last_marks"]) == ("provisional", None)

    # The parent's review queue still has the mark to check.
    [queued] = world.client.get("/evaluations/review-queue", headers=parent).json()
    assert queued["evaluation"]["marks_awarded"] == 3


def test_once_checked_she_sees_the_mark(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    evaluation = answer(world, student)
    done = world.client.post(f"/evaluations/{evaluation['id']}/override", headers=parent, json={"marks_awarded": 3})
    assert done.status_code == 200, done.text
    checked = world.client.get(f"/evaluations/{evaluation['id']}", headers=student).json()
    assert (checked["status"], checked["marks_awarded"], checked["pending"]) == ("overridden", 3, None)
