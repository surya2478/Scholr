"""Daily practice set and past-paper hub through the real API and RLS (docs/STUDENT-APP.md step 4).

The marker is the scripted transport (tests/fixtures/llm.py). Question stems are fixture text for these tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import set_rls_context
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.learn.models import Lesson
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

        def item(**overrides: Any) -> Any:
            values: dict[str, Any] = {
                "tenant_id": w.tenant_id,
                "subject_id": subject_id,
                "origin": "school",
                "source_ref": f"test/{uuid4().hex[:12]}",
                "stem": "Fixture: find the circumference of a circle of radius 2 cm.",
                "marks": 2,
                "command_word": "find",
                "objective_ids": [objective],
                "answer_spec": NUMERIC,
                "mark_scheme": {"text": "M1 2 x pi x 2\nA1 12.6", "source": "test_fixture"},
                "verification_status": "verified",
                "calculator_allowed": True,
            }
            values.update(overrides)
            row = QuestionItem(**values)
            s.add(row)
            s.flush()
            return row.id

        ids = {
            "school_a": item(),
            "school_b": item(),
            "reserved": item(reserved_for_study=True),
            # Every question here is worth 2: the scripted marker awards 2, and a correct answer given fewer marks
            # than the question is worth goes to review (AC-E2) — which question the set answers first is seeded.
            "old_paper": item(origin="past_paper", source_ref="0580/21/MJ99/Q3"),
            "new_paper": item(origin="past_paper", source_ref="0580/21/MJ98/Q1(a)"),
            "untagged": item(origin="past_paper", source_ref="0580/22/MJ98/Q9", objective_ids=[]),
            "reserved_paper": item(origin="past_paper", source_ref="0580/21/MJ98/Q2", reserved_for_study=True),
        }
        # A stored lesson, so she can read it and the topic becomes Introduced (a daily-set claim).
        s.add(
            Lesson(
                tenant_id=w.tenant_id,
                subject_id=subject_id,
                objective_id=objective,
                status="ready",
                retrieval_state="HIGH",
                content={"summary": "", "sections": [], "key_terms": [], "worked_examples": [], "pitfalls": []},
                source_chunk_ids=[],
                corpus_key="fixture",
                checks={},
                guard_version="test",
                prompt_version="test",
                model="test",
                generated_at=datetime.now(UTC),
            )
        )
    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(settings=get_settings(), session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        **vars(w), **ids, objective=str(objective), subject_id=str(subject_id), transport=transport, client=client
    )


def answer(world: SimpleNamespace, headers: dict[str, str], item_id: str) -> None:
    attempt = world.client.post(
        "/attempts",
        headers=headers,
        json={"question_item_id": item_id, "idempotency_key": f"key-{uuid4().hex}", "final_answer": "12.6"},
    ).json()
    world.transport.reply(
        {
            "awards": [
                {"code": "M1", "awarded": True, "reason": "method"},
                {"code": "A1", "awarded": True, "reason": "answer"},
            ],
            "marks_awarded": 2,
            "final_answer_correct": True,
            "feedback_summary": "Correct.",
            "what_went_well": "Right formula.",
            "next_step": "Try arc length.",
            "mistakes": [],
            "confidence": 0.9,
        }
    )
    assert world.client.post(f"/attempts/{attempt['id']}/evaluate", headers=headers).status_code == 200


def test_the_daily_set_is_fixed_for_the_day_and_tracks_her_answers(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204

    first = world.client.get("/practice/daily", headers=student).json()
    ids = [x["item_id"] for x in first["items"]]
    assert ids and set(ids) <= {str(world.school_a), str(world.school_b), str(world.old_paper), str(world.new_paper)}
    assert str(world.reserved) not in ids and str(world.reserved_paper) not in ids
    assert all(x["reason"] and x["status"] == "to_do" for x in first["items"])
    assert (first["done"], first["total"]) == (0, len(ids))

    answer(world, student, ids[0])
    again = world.client.get("/practice/daily", headers=student).json()
    assert [x["item_id"] for x in again["items"]] == ids  # answering does not reshuffle the set
    assert (again["items"][0]["status"], again["items"][0]["marks_awarded"], again["done"]) == ("marked", 2, 1)
    assert world.client.get("/practice/daily", headers=parent).json()["done"] == 1  # the parent sees the same set


def test_the_past_paper_hub_groups_by_chapter_newest_first_and_shows_her_last_try(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    hub = world.client.get(f"/learn/subjects/{world.subject_id}/past-papers", headers=student).json()
    served = {i["id"] for c in hub["chapters"] for i in c["items"]}
    assert str(world.reserved_paper) not in served and str(world.school_a) not in served  # papers only, none reserved
    tagged = next(c for c in hub["chapters"] if c["id"] is not None)
    assert [i["series"] for i in tagged["items"]] == ["MJ99", "MJ98"]  # newest series first
    assert hub["chapters"][-1]["name"] == "Not tagged to a topic yet"
    assert [i["id"] for i in hub["chapters"][-1]["items"]] == [str(world.untagged)]
    assert (hub["total"], hub["attempted"]) == (3, 0)

    answer(world, student, str(world.new_paper))
    hub = world.client.get(f"/learn/subjects/{world.subject_id}/past-papers", headers=student).json()
    [tried] = [i for c in hub["chapters"] for i in c["items"] if i["id"] == str(world.new_paper)]
    assert (tried["last_status"], tried["last_marks"], hub["attempted"]) == ("marked", 2, 1)
