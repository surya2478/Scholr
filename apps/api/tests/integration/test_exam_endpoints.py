"""Integration tests for Examinations Hub and Topic Question Selector endpoints."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import set_rls_context
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db

Auth = Callable[..., dict[str, str]]
NUMERIC = {"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3", "accept_ranges": []}


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        objective, subject_id = s.execute(
            select(LearningObjective.id, Topic.subject_id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(1)
        ).one()

        item = QuestionItem(
            tenant_id=w.tenant_id,
            subject_id=subject_id,
            origin="past_paper",
            source_ref=f"test/exam/{uuid4().hex[:8]}",
            stem="Fixture: Calculate the hypotenuse of a right-angled triangle with sides 3 and 4.",
            marks=3,
            command_word="calculate",
            objective_ids=[objective],
            answer_spec=NUMERIC,
            mark_scheme={"text": "M1 3^2 + 4^2\nA1 5", "source": "test_fixture"},
            verification_status="verified",
            calculator_allowed=True,
        )
        s.add(item)
        s.flush()
        item_id = item.id

    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(settings=get_settings(), session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        client=client,
        tenant_id=w.tenant_id,
        student_id=w.student_id,
        subject_id=subject_id,
        objective_id=objective,
        item_id=item_id,
    )


def test_questions_by_objectives_integration(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    res = world.client.post(
        "/practice/questions/by-objectives",
        json={"subject_id": str(world.subject_id), "objective_ids": [str(world.objective_id)], "limit": 5},
        headers=student,
    )
    assert res.status_code == 200
    questions = res.json()
    assert isinstance(questions, list)
    assert len(questions) >= 1
    assert any(q["id"] == str(world.item_id) for q in questions)


def test_assessment_from_topics_integration(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    res = world.client.post(
        "/assessments/from-topics",
        json={
            "subject_id": str(world.subject_id),
            "title": "Term 1 Mathematics Comprehensive Exam",
            "exam_category": "term",
            "objective_ids": [str(world.objective_id)],
            "target_marks": 30,
            "duration_minutes": 60,
        },
        headers=student,
    )
    assert res.status_code == 201
    assessment = res.json()
    # Her own exam, not a past-paper sitting: sat under exam conditions but never weighed as exam evidence.
    assert assessment["kind"] == "topic_exam" and assessment["form_code"] is None and assessment["no_help"]
    assert assessment["config"]["title"] == "Term 1 Mathematics Comprehensive Exam"
    assert assessment["config"]["duration_min"] == 60
    assert assessment["total_marks"] <= 30 and len(assessment["items"]) >= 1


def test_no_exam_is_set_when_the_chosen_topics_have_no_questions(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    res = world.client.post(
        "/assessments/from-topics",
        json={
            "subject_id": str(world.subject_id),
            "title": "Nothing here",
            "exam_category": "practice_exam",
            "objective_ids": [str(uuid4())],
        },
        headers=student,
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "no_questions_for_topics"


def test_bookmarks_follow_her_record_and_only_she_changes_them(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    url = f"/bookmarks/{world.item_id}"
    assert world.client.put(url, json={"tag": "examiner_trap", "note": "sign"}, headers=student).status_code == 204
    assert world.client.put(url, json={"tag": "must_revise"}, headers=student).status_code == 204  # retag, no copy
    saved = world.client.get("/bookmarks", headers=student).json()
    assert [(b["question_item_id"], b["tag"], b["note"]) for b in saved] == [(str(world.item_id), "must_revise", None)]
    assert len(world.client.get("/bookmarks", headers=parent).json()) == 1  # a parent can see them
    assert world.client.put(url, json={"tag": "calc_heavy"}, headers=parent).status_code == 403
    assert world.client.put(f"/bookmarks/{uuid4()}", json={}, headers=student).status_code == 404
    assert world.client.delete(url, headers=student).status_code == 204
    assert world.client.get("/bookmarks", headers=student).json() == []


def test_command_words_come_only_from_a_checked_source(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    maths = world.client.get(f"/subjects/{world.subject_id}/command-words", headers=student).json()
    assert maths == {"source": None, "definitions": {}}  # no checked table for 0580: nothing is shown
