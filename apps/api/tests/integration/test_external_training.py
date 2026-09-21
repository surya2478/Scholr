"""Phase 3 end to end: log an IIT Foundation class, trace it, and let it nudge (never take over) the day.

AC-X1 seeding is additive, AC-X3 external logs never touch mastery, AC-X4 one event per log,
AC-X9 one reinforcement item a day, AC-X10 no plan item is ever an external objective,
AC-X11/X12 the surfaces say where a suggestion came from.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import API_ROOT
from app.core.db import set_rls_context
from app.main import create_app
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events import service as events
from app.modules.events.models import LearningEvent
from app.modules.mastery import service as mastery
from app.modules.mastery.models import MasteryState
from app.seed.concepts import load as load_concepts
from app.seed.concepts import seed_concepts
from app.seed.curriculum import load_file, seed_curriculum

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

CURRICULUM_DIR = API_ROOT.parents[1] / "content" / "curriculum"
IIT_MATHS = CURRICULUM_DIR / "iit-maths-grade9.yaml"
CONCEPT_MAP = CURRICULUM_DIR / "concepts-maths-grade9.yaml"
HERONS_FORMULA = "L17"  # the lesson the tests struggle with; its IGCSE ground is triangle area (27.2)


def _objectives(factory, subject_code: str) -> dict[str, object]:  # noqa: ANN001
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
        seed_curriculum(s, load_file(IIT_MATHS))
        seed_concepts(s, load_concepts(CONCEPT_MAP))
    iit = _objectives(w.factory, "iit-maths")
    igcse = _objectives(w.factory, "igcse-maths")
    client = TestClient(create_app(session_factory=w.factory))
    return SimpleNamespace(
        **vars(w),
        client=client,
        iit=iit,
        igcse=igcse,
        iit_subject_id=iit[HERONS_FORMULA][1],
        igcse_subject_id=igcse["27.2"][1],
    )


def log_body(world: SimpleNamespace, **overrides: object) -> dict[str, object]:
    lesson = str(world.iit[HERONS_FORMULA][0])
    body: dict[str, object] = {
        "subject_id": str(world.iit_subject_id),
        "kind": "class",
        "title": "Saturday maths class",
        "occurred_on": date.today().isoformat(),
        "duration_min": 120,
        "objective_ids": [lesson],
        "weak_objective_ids": [lesson],
        "score": 4,
        "max_score": 20,
        "weaknesses": ["ran out of time"],
    }
    body.update(overrides)
    return body


def test_seeding_the_external_curriculum_leaves_igcse_untouched(world: SimpleNamespace) -> None:  # AC-X1
    before = len(world.igcse)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_curriculum(s, load_file(IIT_MATHS))  # a second run must change nothing
        seed_concepts(s, load_concepts(CONCEPT_MAP))
    assert len(_objectives(world.factory, "igcse-maths")) == before
    assert len(_objectives(world.factory, "iit-maths")) == 29


def test_a_parent_logs_a_class_and_it_comes_back(world: SimpleNamespace, auth_headers: Auth) -> None:
    parent, student = auth_headers("test|parent"), auth_headers("test|student")
    created = world.client.post("/external-training", headers=parent, json=log_body(world))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["subject_name"] == "IIT Foundation Mathematics"
    assert [lesson["code"] for lesson in body["weak_lessons"]] == [HERONS_FORMULA]
    assert body["score"] == 4 and body["max_score"] == 20

    listed = world.client.get("/external-training", headers=student).json()
    assert [row["id"] for row in listed] == [body["id"]]


def test_one_event_per_log_and_it_carries_no_wording(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-X4
    world.client.post("/external-training", headers=auth_headers("test|parent"), json=log_body(world))
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        rows = list(s.scalars(select(LearningEvent).where(LearningEvent.type == "external_training_logged")))
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["weak_lessons"] == 1 and payload["score"] == 4
    assert "ran out of time" not in str(payload)
    assert rows[0].student_id == world.student_id


def test_a_subject_scholr_owns_cannot_be_logged_as_training(world: SimpleNamespace, auth_headers: Auth) -> None:
    body = log_body(world, subject_id=str(world.igcse_subject_id), objective_ids=[], weak_objective_ids=[])
    refused = world.client.post("/external-training", headers=auth_headers("test|parent"), json=body)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "subject_not_external"


def test_lessons_must_belong_to_the_course(world: SimpleNamespace, auth_headers: Auth) -> None:
    stray = str(world.igcse["27.2"][0])
    body = log_body(world, objective_ids=[stray], weak_objective_ids=[stray])
    refused = world.client.post("/external-training", headers=auth_headers("test|parent"), json=body)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "objective_not_in_subject"


def test_weak_lessons_must_be_among_the_lessons_covered(world: SimpleNamespace, auth_headers: Auth) -> None:
    body = log_body(world, objective_ids=[], weak_objective_ids=[str(world.iit[HERONS_FORMULA][0])])
    refused = world.client.post("/external-training", headers=auth_headers("test|parent"), json=body)
    assert refused.status_code == 422


def test_an_external_log_never_moves_mastery(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-X3
    objective_id = world.igcse["27.2"][0]
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
                    "marks_awarded": 2,
                    "marks_available": 3,
                    "help_level": 1,
                    "evaluation_confidence": 0.9,
                    "status": "final",
                },
            )
            for h in (1, 2, 3)
        ]
        mastery.project(s, new, tenant_id=world.tenant_id, now=now)

    def snapshot() -> list[tuple[object, int, float, int]]:
        with world.factory() as s, s.begin():
            set_rls_context(s, user_id=None, role="system")
            return sorted(
                (row.objective_id, row.level, row.score, row.evidence_count)
                for row in s.scalars(select(MasteryState).where(MasteryState.student_id == world.student_id))
            )

    before = snapshot()
    world.client.post("/external-training", headers=auth_headers("test|parent"), json=log_body(world))
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        mastery.rebuild(s, tenant_id=world.tenant_id, student_id=world.student_id, now=now)
    assert snapshot() == before


def test_the_summary_points_at_igcse_work_and_says_why(world: SimpleNamespace, auth_headers: Auth) -> None:
    parent = auth_headers("test|parent")
    world.client.post("/external-training", headers=parent, json=log_body(world))
    summary = world.client.get(f"/external-training/summary?student_id={world.student_id}", headers=parent).json()

    standing = summary["subjects"][0]
    assert standing["subject_name"] == "IIT Foundation Mathematics"
    assert standing["sessions"] == 1 and standing["minutes"] == 120
    assert standing["lessons_total"] == 29
    assert [lesson["code"] for lesson in standing["weak_lessons"]] == [HERONS_FORMULA]

    targets = summary["reinforcement"]
    assert targets, "a weak lesson must point at something to do"
    # AC-X10: every suggestion is an IGCSE objective, never the IIT lesson itself.
    assert {t["subject_name"] for t in targets} == {"Mathematics"}
    assert str(world.iit[HERONS_FORMULA][0]) not in {t["objective_id"] for t in targets}
    # AC-X12: the reason names the class topic.
    assert all("Heron" in t["reason"] for t in targets)
    assert any(t["objective_code"] == "27.2" for t in targets)
    # AC-X11: the note explains a mapping that goes beyond the IGCSE syllabus.
    assert any(t["note"] and "0580 does not examine" in t["note"] for t in targets)


def test_the_day_gets_one_reinforcement_block_at_most(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-X9
    parent, student = auth_headers("test|parent"), auth_headers("test|student")
    world.client.put(f"/students/{world.student_id}/availability", headers=parent, json={"minutes": [180] * 7})
    lessons = [str(world.iit[code][0]) for code in ("L17", "L16", "L15")]
    for lesson in lessons:
        world.client.post(
            "/external-training",
            headers=parent,
            json=log_body(world, objective_ids=[lesson], weak_objective_ids=[lesson]),
        )

    plan = world.client.get("/plan/today", headers=student).json()
    items = [i for i in plan["items"] if i["kind"] == "reinforcement"]
    assert len(items) <= 1
    if items:
        assert items[0]["est_minutes"] <= 20
        assert items[0]["subject_name"] == "Mathematics"  # AC-X10
        assert "class on" in items[0]["reason"]  # AC-X12
    assert all(i["subject_id"] != str(world.iit_subject_id) for i in plan["items"])


# --- a subject Scholr has planned but does not yet teach (IGCSE Physics 0625) ---------------------------------

IIT_PHYSICS = CURRICULUM_DIR / "iit-physics-grade9.yaml"
IGCSE_PHYSICS = CURRICULUM_DIR / "igcse-physics-0625.yaml"
PHYSICS_CONCEPTS = CURRICULUM_DIR / "concepts-physics-grade9.yaml"
NEWTONS_SECOND_LAW = "L13"


@pytest.fixture
def physics_world(world: SimpleNamespace) -> SimpleNamespace:
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_curriculum(s, load_file(IIT_PHYSICS))
        seed_curriculum(s, load_file(IGCSE_PHYSICS))
        seed_concepts(s, load_concepts(PHYSICS_CONCEPTS))
    iit_physics = _objectives(world.factory, "iit-physics")
    return SimpleNamespace(
        **vars(world),
        iit_physics=iit_physics,
        physics_subject_id=iit_physics[NEWTONS_SECOND_LAW][1],
    )


def physics_log(world: SimpleNamespace) -> dict[str, object]:
    lesson = str(world.iit_physics[NEWTONS_SECOND_LAW][0])
    return {
        "subject_id": str(world.physics_subject_id),
        "kind": "class",
        "title": "Thursday physics class",
        "occurred_on": date.today().isoformat(),
        "duration_min": 120,
        "objective_ids": [lesson],
        "weak_objective_ids": [lesson],
        "score": 5,
        "max_score": 20,
    }


def test_a_planned_subject_is_suggested_as_revision_not_practice(
    physics_world: SimpleNamespace, auth_headers: Auth
) -> None:
    """0625 has a syllabus but no questions yet, so the trace may name a topic — not set work on it."""
    parent = auth_headers("test|parent")
    physics_world.client.post("/external-training", headers=parent, json=physics_log(physics_world))
    summary = physics_world.client.get(
        f"/external-training/summary?student_id={physics_world.student_id}", headers=parent
    ).json()

    physics = [t for t in summary["reinforcement"] if t["subject_name"] == "Physics"]
    assert physics, "an IIT physics class must now point at IGCSE Physics"
    assert all(t["practicable"] is False for t in physics)
    assert any(t["objective_code"] == "1.5" for t in physics)  # Forces
    assert all("Newton's second law" in t["reason"] for t in physics)


def test_the_planner_never_schedules_a_subject_it_cannot_set_work_in(
    physics_world: SimpleNamespace, auth_headers: Auth
) -> None:  # AC-X9
    parent, student = auth_headers("test|parent"), auth_headers("test|student")
    physics_world.client.put(
        f"/students/{physics_world.student_id}/availability", headers=parent, json={"minutes": [180] * 7}
    )
    physics_world.client.post("/external-training", headers=parent, json=physics_log(physics_world))

    plan = physics_world.client.get("/plan/today", headers=student).json()
    assert all(item["subject_name"] != "Physics" for item in plan["items"])


def test_a_planned_subject_cannot_be_logged_as_external_training(
    physics_world: SimpleNamespace, auth_headers: Auth
) -> None:
    igcse_physics = _objectives(physics_world.factory, "igcse-physics")
    body = {
        **physics_log(physics_world),
        "subject_id": str(igcse_physics["1.5"][1]),
        "objective_ids": [],
        "weak_objective_ids": [],
    }
    refused = physics_world.client.post("/external-training", headers=auth_headers("test|parent"), json=body)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "subject_not_external"


def test_the_day_still_finds_maths_when_the_science_classes_are_louder(
    physics_world: SimpleNamespace, auth_headers: Auth
) -> None:
    """A run of bad physics classes must not starve the day of the maths work Scholr can actually set.

    Physics is only planned, so its targets can never be scheduled. If the planner filtered the finished
    top-N list instead of narrowing the search, three fresh physics logs would push every maths target out
    of range and the day would get no reinforcement at all.
    """
    parent, student = auth_headers("test|parent"), auth_headers("test|student")
    physics_world.client.put(
        f"/students/{physics_world.student_id}/availability", headers=parent, json={"minutes": [180] * 7}
    )
    for code in ("L13", "L14", "L12"):
        lesson = str(physics_world.iit_physics[code][0])
        physics_world.client.post(
            "/external-training",
            headers=parent,
            json={**physics_log(physics_world), "objective_ids": [lesson], "weak_objective_ids": [lesson]},
        )
    # An older, milder maths class: it loses on the combined list but is the only thing that can be practised.
    physics_world.client.post(
        "/external-training",
        headers=parent,
        json=log_body(physics_world, occurred_on=(date.today() - timedelta(days=5)).isoformat()),
    )

    plan = physics_world.client.post("/plan/regenerate", headers=student).json()
    reinforcement = [i for i in plan["items"] if i["kind"] == "reinforcement"]
    assert len(reinforcement) == 1
    assert reinforcement[0]["subject_name"] == "Mathematics"
