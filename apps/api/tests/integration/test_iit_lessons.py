"""The IIT Foundation area by lesson (docs/STUDENT-APP.md step 5), through the real API and RLS.

An IIT lesson page never teaches the lesson (PHASE-3 §1): it shows her logged classes on it, the IGCSE ground
underneath from the concept map, and a warm-up from that ground. Question stems are fixture text.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import API_ROOT
from app.core.db import set_rls_context
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.seed.concepts import load as load_concepts
from app.seed.concepts import seed_concepts
from app.seed.curriculum import load_file, seed_curriculum

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

CURRICULUM_DIR = API_ROOT.parents[1] / "content" / "curriculum"
HERONS_FORMULA = "L17"  # IIT Maths lesson whose IGCSE ground includes triangle area (27.2)
TRIANGLE_AREA = "27.2"
SQUARE_ROOTS = "5.1"


def objectives(factory: Any, subject_code: str) -> dict[str, tuple[Any, Any]]:
    with factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        rows = s.execute(
            select(LearningObjective.code, LearningObjective.id, Topic.subject_id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == subject_code)
        ).all()
    return {code: (oid, sid) for code, oid, sid in rows}


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_curriculum(s, load_file(CURRICULUM_DIR / "iit-maths-grade9.yaml"))
        seed_concepts(s, load_concepts(CURRICULUM_DIR / "concepts-maths-grade9.yaml"))
    iit, igcse = objectives(w.factory, "iit-maths"), objectives(w.factory, "igcse-maths")
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        item = QuestionItem(
            tenant_id=w.tenant_id,
            subject_id=igcse[TRIANGLE_AREA][1],
            origin="school",
            source_ref=f"test/{uuid4().hex[:12]}",
            stem="Fixture: find the area of a triangle with base 6 cm and height 4 cm.",
            marks=2,
            command_word="find",
            # Tagged to two objectives Heron's formula rests on: it must still be set only once.
            objective_ids=[igcse[TRIANGLE_AREA][0], igcse[SQUARE_ROOTS][0]],
            answer_spec={"type": "numeric", "answer": "12", "exact": "12", "accuracy": "sf3"},
            mark_scheme={"text": "M1 1/2 x 6 x 4\nA1 12", "source": "test_fixture"},
            verification_status="verified",
        )
        s.add(item)
        s.flush()
        item_id = item.id
    client = TestClient(create_app(session_factory=w.factory))
    return SimpleNamespace(
        **vars(w),
        client=client,
        lesson=str(iit[HERONS_FORMULA][0]),
        iit_subject=str(iit[HERONS_FORMULA][1]),
        triangle=str(igcse[TRIANGLE_AREA][0]),
        item_id=str(item_id),
    )


def test_an_iit_lesson_shows_the_ground_underneath_and_a_warm_up_never_a_lesson(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    topic = world.client.get(f"/learn/objectives/{world.lesson}", headers=auth_headers("test|student")).json()
    assert topic["subject"]["stage"] == "external"
    assert topic["lesson_available"] is False and topic["lesson"] is None  # Scholr does not teach it
    assert topic["check_yourself"] == [] and topic["exam_questions"] == []
    assert "IIT Foundation classes" in topic["notice"]
    ground = {g["objective_id"]: g for g in topic["external"]["ground"]}
    assert world.triangle in ground, "Heron's formula rests on the area of a triangle"
    assert all(g["subject_name"] != "IIT Foundation Mathematics" for g in ground.values())  # IGCSE only (AC-X10)
    warm_up = [w["id"] for w in topic["external"]["warm_up"]]
    assert warm_up == [world.item_id]
    assert len(warm_up) == len(set(warm_up)), "a question tagged to two objectives underneath is set once"
    assert topic["external"]["classes"] == []


def test_a_logged_class_appears_on_its_lesson_and_in_the_chapter_list(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    logged = world.client.post(
        "/external-training",
        headers=student,
        json={
            "subject_id": world.iit_subject,
            "kind": "class",
            "title": "Heron's formula",
            "occurred_on": date.today().isoformat(),
            "objective_ids": [world.lesson],
            "weak_objective_ids": [world.lesson],
            "score": 6,
            "max_score": 10,
        },
    )
    assert logged.status_code == 201, logged.text

    topic = world.client.get(f"/learn/objectives/{world.lesson}", headers=student).json()
    [entry] = topic["external"]["classes"]
    assert (entry["title"], entry["score"], entry["max_score"], entry["struggled"]) == ("Heron's formula", 6, 10, True)

    view = world.client.get(f"/learn/subjects/{world.iit_subject}", headers=student).json()

    def find(chapters: list[dict]) -> dict | None:
        for chapter in chapters:
            for o in chapter["objectives"]:
                if o["id"] == world.lesson:
                    return o
            if (found := find(chapter["chapters"])) is not None:
                return found
        return None

    card = find(view["chapters"])
    assert card is not None and (card["classes"], card["struggled"]) == (1, True)
    assert card["mastery_level"] is None, "an external lesson never has Scholr mastery (AC-X3)"
