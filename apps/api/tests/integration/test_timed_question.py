"""This week's timed question through the real API (improvement 4).

One real long answer a week, under exam conditions, timed at her papers' own pace. The Sociology syllabus and its
exam components are the real seed; the questions below are fixture text written for this test.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import API_ROOT
from app.core.db import set_rls_context
from app.core.ids import uuid7
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.enrollment.models import Enrollment
from app.seed.curriculum import load_file, seed_curriculum

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
        s.add(Enrollment(tenant_id=w.tenant_id, student_id=w.student_id, subject_id=subject_id, exam_session="2027-06"))
        ids = {}
        for ref, marks, command in (("Q1(a)", 2, "define"), ("Q2(f)", 14, "evaluate"), ("Q3(e)", 8, "discuss")):
            ids[ref] = uuid7()
            s.add(
                QuestionItem(
                    id=ids[ref],
                    tenant_id=w.tenant_id,
                    subject_id=subject_id,
                    origin="past_paper",
                    source_ref=f"test/0495/fixture/{ref}",
                    stem=f"Fixture stem for {ref}",
                    marks=marks,
                    command_word=command,
                    objective_ids=[objective_id],
                    verification_status="verified",
                    mark_scheme={"text": "fixture mark scheme"},
                )
            )
    client = TestClient(create_app(session_factory=w.factory))
    return SimpleNamespace(**vars(w), client=client, subject_id=subject_id, items=ids)


def test_this_weeks_question_is_a_real_long_answer_at_her_exams_pace(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    [q] = world.client.get("/timed-questions", headers=student).json()  # Maths is marked in parts: none there
    assert q["subject_id"] == str(world.subject_id) and q["status"] == "to_do" and q["assessment_id"] is None
    assert q["item"]["question_item_id"] == str(world.items["Q2(f)"])  # the biggest long answer; never the 2-marker
    # Both 0495 papers: 225 minutes for 160 marks, so 14 marks is 19.7 minutes, rounded up.
    assert (q["item"]["marks"], q["item"]["minutes"]) == (14, 20)


def test_a_subject_she_is_not_enrolled_in_has_none(world: SimpleNamespace, auth_headers: Auth) -> None:
    maths = world.client.get("/subjects", headers=auth_headers("test|student")).json()
    maths_id = next(x["id"] for x in maths if x["code"] == "igcse-maths")
    refused = world.client.post(f"/subjects/{maths_id}/timed-question", headers=auth_headers("test|student"))
    assert refused.status_code == 404  # enrolled, but marked in parts: no long answer to time


def test_starting_it_starts_a_timed_sitting_once_a_week(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    c = world.client
    assert c.post(f"/subjects/{world.subject_id}/timed-question", headers=parent).status_code == 403

    started = c.post(f"/subjects/{world.subject_id}/timed-question", headers=student)
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["status"] == "in_progress" and body["assessment_id"]
    again = c.post(f"/subjects/{world.subject_id}/timed-question", headers=student).json()
    assert again["assessment_id"] == body["assessment_id"]  # one a week: the same sitting comes back

    sitting = c.get(f"/assessments/{body['assessment_id']}", headers=student).json()
    assert (sitting["kind"], sitting["status"], sitting["no_help"]) == ("exam_style", "in_progress", True)
    assert sitting["config"]["duration_min"] == 20 and sitting["config"]["weekly_timed"] == body["week_start"]
    assert [i["question_item_id"] for i in sitting["items"]] == [str(world.items["Q2(f)"])]

    attempt = c.post(
        "/attempts",
        headers=student,
        json={
            "question_item_id": str(world.items["Q2(f)"]),
            "assessment_id": body["assessment_id"],
            "idempotency_key": "timed-0001-fixture",
            "working": "An answer written against the clock.",
        },
    )
    assert attempt.status_code == 201, attempt.text
    assert c.post(f"/assessments/{body['assessment_id']}/submit", headers=student).status_code == 200
    [done] = c.get("/timed-questions", headers=student).json()
    assert done["status"] == "submitted" and done["minutes_used"] is not None and done["over_time"] is False
