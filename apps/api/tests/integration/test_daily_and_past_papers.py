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


def answer(world: SimpleNamespace, headers: dict[str, str], item_id: str, seconds: int | None = None) -> None:
    attempt = world.client.post(
        "/attempts",
        headers=headers,
        json={
            "question_item_id": item_id,
            "idempotency_key": f"key-{uuid4().hex}",
            "final_answer": "12.6",
            "time_spent_s": seconds,
        },
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

    assert first["answering_minutes"] == 0 and first["external_minutes"] == 0
    answer(world, student, ids[0], seconds=150)
    again = world.client.get("/practice/daily", headers=student).json()
    assert again["answering_minutes"] == 2  # 150 s, as timed by the answer box: nothing estimated from marks
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


def second_objective_with_questions(world: SimpleNamespace) -> str:
    """A second taught topic with a lesson and its own bank items, added after today's set was built.

    Today's set is fixed for the day, so this never changes it — it gives tomorrow's preview something to find.
    """
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        objective = s.scalars(
            select(LearningObjective.id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .offset(1)
            .limit(1)
        ).one()
        for _ in range(2):
            s.add(
                QuestionItem(
                    tenant_id=world.tenant_id,
                    subject_id=world.subject_id,
                    origin="school",
                    source_ref=f"test/{uuid4().hex[:12]}",
                    stem="Fixture: find the area of a circle of radius 3 cm.",
                    marks=2,
                    command_word="find",
                    objective_ids=[objective],
                    answer_spec=NUMERIC,
                    mark_scheme={"text": "M1 pi x 3^2\nA1 28.3", "source": "test_fixture"},
                    verification_status="verified",
                    calculator_allowed=True,
                )
            )
        s.add(
            Lesson(
                tenant_id=world.tenant_id,
                subject_id=world.subject_id,
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
    return str(objective)


def test_tomorrow_is_previewed_only_once_todays_set_is_finished(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204

    first = world.client.get("/practice/daily", headers=student).json()
    ids = [x["item_id"] for x in first["items"]]
    assert first["tomorrow"] == []  # nothing is promised while there is still something to do today

    answer(world, student, ids[0])
    partway = world.client.get("/practice/daily", headers=student).json()
    assert partway["done"] < partway["total"] and partway["tomorrow"] == []

    # A topic she has only read, with questions she has not answered: tomorrow has something real to start from.
    second = second_objective_with_questions(world)
    assert world.client.post(f"/learn/objectives/{second}/read", headers=student).status_code == 204
    for item_id in ids[1:]:
        answer(world, student, item_id)

    done = world.client.get("/practice/daily", headers=student).json()
    assert done["done"] == done["total"] > 0
    topics = done["tomorrow"]
    assert second in [t["objective_id"] for t in topics]
    assert 0 < len(topics) <= 3  # daily.PREVIEW_SIZE, and one line per topic
    assert len({t["objective_id"] for t in topics}) == len(topics)
    assert all(t["objective_code"] and t["subject_name"] and t["reason"] and t["reason_code"] for t in topics)
    assert [t["reason_code"] for t in topics] == sorted(
        (t["reason_code"] for t in topics),
        key=lambda code: (
            ["open_mistake_high", "open_mistake_medium", "retention_high", "retention_medium"].index(code)
            if code in ("open_mistake_high", "open_mistake_medium", "retention_high", "retention_medium")
            else 9
        ),
    )  # the order of claim the rule uses: mistakes, then retention, then topics only read


def test_tomorrow_never_names_a_topic_whose_questions_she_has_just_answered(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204
    world.client.get("/practice/daily", headers=student)

    # Every servable question on this topic, not only the ones today's set happened to pick.
    for item_id in (world.school_a, world.school_b, world.old_paper, world.new_paper):
        answer(world, student, str(item_id))

    done = world.client.get("/practice/daily", headers=student).json()
    assert done["done"] == done["total"] > 0
    # The rule will not set those questions again for two weeks, so the topic has nothing left to offer and the
    # preview leaves it out rather than promising work that is not there.
    assert world.objective not in [t["objective_id"] for t in done["tomorrow"]]


def test_the_three_doors_are_always_served_with_minutes_from_their_own_content(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204

    data = world.client.get("/practice/daily", headers=student).json()
    doors = {d["key"]: d for d in data["doors"]}
    assert set(doors) == {"quick", "today", "deep"}  # all three, always: a hidden door reads as a missing feature
    assert all(d["text"] and (d["open"] or d["closed_reason"]) for d in doors.values())

    # Today's door: a minute a mark over the questions she has not answered, and it matches the set itself.
    to_do = [x for x in data["items"] if x["status"] == "to_do"]
    assert doors["today"]["questions"] == len(to_do)
    assert doors["today"]["minutes"] == sum(max(1, x["marks"]) for x in to_do)

    # The long door opens the first topic the set still has work on, and names the parts she has left. Every
    # fixture question here is tagged to that one topic.
    deep = doors["deep"]
    assert deep["objective_id"] == to_do[0]["objective_id"] == world.objective
    assert deep["open"] and deep["minutes"] > 0 and deep["parts"]
    topic = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    first_left = next(s for s in topic["steps"] if not s["done"])
    assert deep["minutes"] == first_left["minutes"] and deep["parts"][0] == first_left["label"]  # the page's own

    # Nothing in this world is due for revision, so the short door is closed and says why rather than vanishing.
    assert doors["quick"]["open"] is False
    assert doors["quick"]["closed_reason"] and doors["quick"]["questions"] == 0


def test_every_door_closes_with_its_reason_once_the_set_is_finished(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204
    first = world.client.get("/practice/daily", headers=student).json()
    for item_id in [x["item_id"] for x in first["items"]]:
        answer(world, student, item_id)

    done = world.client.get("/practice/daily", headers=student).json()
    doors = {d["key"]: d for d in done["doors"]}
    assert done["done"] == done["total"] > 0
    assert [d["open"] for d in doors.values()] == [False, False, False]
    assert all(d["closed_reason"] and d["minutes"] == 0 for d in doors.values())
    assert doors["deep"]["objective_id"] is None  # no topic left to offer, so none is named


def test_the_long_door_never_offers_a_topic_with_nothing_left_on_it(world: SimpleNamespace, auth_headers: Auth) -> None:
    """Found on her own record, 25 Oct 2026: the door named topic 33.3 with "about 0 min" and told her she had
    finished today's set while none of its six questions was answered. A topic page counts a part as done once
    she has answered any question in it, so a page can have nothing left while the set still holds questions from
    that topic. The door now looks past such a topic, and never gives a reason that is false."""
    student = auth_headers("test|student")
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204
    world.client.get("/practice/daily", headers=student)

    # Lesson read and every servable question on this topic answered: its page has nothing left to offer. Which
    # of them today's set happened to pick does not matter — the set's tie-break is a hash of her id and the day.
    for item_id in (world.school_a, world.school_b, world.old_paper, world.new_paper):
        answer(world, student, str(item_id))
    page = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    assert sum(s["minutes"] for s in page["steps"] if not s["done"]) == 0

    data = world.client.get("/practice/daily", headers=student).json()
    deep = next(d for d in data["doors"] if d["key"] == "deep")
    assert deep["objective_id"] != world.objective  # the exhausted topic is never the one offered

    if deep["open"]:  # another of today's topics has something left: the minutes are that part's own
        assert deep["minutes"] > 0 and deep["parts"]
        other = world.client.get(f"/learn/objectives/{deep['objective_id']}", headers=student).json()
        first_left = next(s for s in other["steps"] if not s["done"])
        assert deep["minutes"] == first_left["minutes"] and deep["parts"][0] == first_left["label"]
    else:
        assert deep["minutes"] == 0 and deep["objective_id"] is None and deep["closed_reason"]
        if data["done"] < data["total"]:  # work remains, so it must not claim she has finished
            assert "already read and tried" in deep["closed_reason"]
