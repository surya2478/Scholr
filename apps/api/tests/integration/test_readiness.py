"""Sociology exam readiness through the real API (Phase 2: AC-R1, AC-R2, AC-R3, AC-R4)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import API_ROOT
from app.core.db import set_rls_context
from app.core.ids import uuid7
from app.jobs import ao_tag
from app.main import create_app
from app.modules.assessment.models import Assessment, QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.seed.curriculum import load_file, seed_curriculum

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

SOCIOLOGY = API_ROOT.parents[1] / "content" / "curriculum" / "igcse-sociology-0495.yaml"
# One real Paper 1, part for part as in the 2025 papers: Q1 compulsory (40 marks), then Q2 or Q3 (40 each).
# The tariffs have to add up — a paper whose questions do not total 40 would make the 80-mark check vacuous.
PAPER = "0495/11/MJ25"
PARTS = [
    ("Q1(a)(i)", 2, "identify"),
    ("Q1(a)(ii)", 4, "explain"),
    ("Q1(a)(iii)", 6, "explain"),
    ("Q1(b)", 2, "state"),
    ("Q1(c)", 4, "explain"),
    ("Q1(d)", 10, "evaluate"),
    ("Q1(e)", 12, "explain"),
    ("Q2(a)(i)", 2, "define"),
    ("Q2(a)(ii)", 2, "define"),
    ("Q2(b)", 2, "give"),
    ("Q2(c)", 6, "explain"),
    ("Q2(d)", 6, "explain"),
    ("Q2(e)", 8, "discuss"),
    ("Q2(f)", 14, "evaluate"),
    ("Q3(a)(i)", 2, "define"),
    ("Q3(a)(ii)", 2, "define"),
    ("Q3(b)", 2, "give"),
    ("Q3(c)", 6, "explain"),
    ("Q3(d)", 6, "explain"),
    ("Q3(e)", 8, "discuss"),
    ("Q3(f)", 14, "evaluate"),
]


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
        for ref, marks, command in PARTS:
            s.add(
                QuestionItem(
                    id=uuid7(),
                    tenant_id=w.tenant_id,
                    subject_id=subject_id,
                    origin="past_paper",
                    source_ref=f"{PAPER}/{ref}",
                    parent_ref=f"{PAPER}/{ref.split('(')[0]}",
                    stem=f"Test stem for {ref}",
                    marks=marks,
                    command_word=command,
                    objective_ids=[objective_id],
                    verification_status="verified",
                    mark_scheme={"points": ["a point"]},
                )
            )
        s.flush()
        report, _spread = ao_tag.run(s, subject_code="igcse-sociology", write=True)
    client = TestClient(create_app(session_factory=w.factory))
    return SimpleNamespace(**vars(w), client=client, subject_id=subject_id, tagged=report.tagged)


def test_the_bank_is_tagged_from_the_syllabus_rule(world: SimpleNamespace) -> None:  # AC-R1
    assert world.tagged == len(PARTS)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        tagged = dict(
            s.execute(
                select(QuestionItem.source_ref, QuestionItem.skill_ids).where(
                    QuestionItem.subject_id == world.subject_id
                )
            ).all()
        )
    # Source-based Paper 1 Q1(a) parts carry AO2 and AO3; short parts AO1 and AO2; 8 marks and above all three.
    assert len(tagged[f"{PAPER}/Q1(a)(i)"]) == 2
    assert len(tagged[f"{PAPER}/Q2(c)"]) == 2
    assert len(tagged[f"{PAPER}/Q2(e)"]) == 3
    assert len(tagged[f"{PAPER}/Q2(f)"]) == 3
    assert all(tags for tags in tagged.values()), "no item may be left untagged"


def test_readiness_refuses_to_judge_without_evidence(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-R2
    body = world.client.get(f"/subjects/{world.subject_id}/readiness", headers=auth_headers("test|student")).json()
    assert body["weighted_share"] is None
    assert {row["band"] for row in body["skills"]} == {"unknown"}
    assert any("nothing here can be judged" in note for note in body["notes"])
    assert body["days_to_exam"] is None or isinstance(body["days_to_exam"], int)
    # Command words are listed with what the bank can offer, even before she has answered any.
    assert {row["command_word"] for row in body["command_words"]} >= {"evaluate", "discuss", "explain"}
    assert all(row["answers"] == 0 for row in body["command_words"])


def test_readiness_counts_each_units_objectives(world: SimpleNamespace, auth_headers: Auth) -> None:
    # Objectives sit under subtopics; the per-unit rows must roll them up, not report zero for every unit.
    body = world.client.get(f"/subjects/{world.subject_id}/readiness", headers=auth_headers("test|student")).json()
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        total = s.scalar(
            select(func.count(LearningObjective.id))
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .where(Topic.subject_id == world.subject_id)
        )
    assert body["topics"], "readiness lists the units"
    assert all(row["objectives_total"] > 0 for row in body["topics"])
    assert sum(row["objectives_total"] for row in body["topics"]) == total


def test_a_paper_is_offered_with_what_it_is_really_worth(world: SimpleNamespace, auth_headers: Auth) -> None:
    papers = world.client.get(f"/subjects/{world.subject_id}/past-papers", headers=auth_headers("test|student")).json()
    paper = next(p for p in papers if p["paper_ref"] == PAPER)
    assert paper["questions"] == len(PARTS), "the bank holds every question"
    assert paper["paper_marks"] == 80, "but a candidate sits 80 marks"
    assert paper["bank_marks"] > paper["paper_marks"]
    assert paper["duration_min"] == 120
    assert paper["sat_on"] is None


def test_a_timed_sitting_is_the_paper_she_would_actually_answer(
    world: SimpleNamespace, auth_headers: Auth
) -> None:  # AC-R3
    student = auth_headers("test|student")
    created = world.client.post(
        f"/subjects/{world.subject_id}/sittings",
        headers=student,
        json={"paper_ref": PAPER, "questions": ["Q2"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["marks"] == 80, "Q1 plus one choice is the real paper total"
    assert body["questions"] == ["Q2"]
    assert body["duration_min"] == 120 and body["minutes_left"] == 120
    assert body["over_time"] is False
    assert body["status"] == "in_progress"

    resumed = world.client.get(f"/sittings/{body['assessment_id']}", headers=student).json()
    assert resumed["assessment_id"] == body["assessment_id"], "starting again resumes, never duplicates"


def test_the_paper_list_offers_the_syllabus_choice(world: SimpleNamespace, auth_headers: Auth) -> None:
    papers = world.client.get(f"/subjects/{world.subject_id}/past-papers", headers=auth_headers("test|student")).json()
    paper = next(p for p in papers if p["paper_ref"] == PAPER)
    assert paper["question_numbers"] == ["Q1", "Q2", "Q3"]
    assert (paper["compulsory"], paper["choose_from"], paper["choose_count"]) == (["Q1"], ["Q2", "Q3"], 1)
    assert paper["in_progress"] is False


def test_a_sitting_is_sat_under_exam_conditions(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-R3
    student, c = auth_headers("test|student"), world.client
    sitting = c.post(
        f"/subjects/{world.subject_id}/sittings", headers=student, json={"paper_ref": PAPER, "questions": ["Q2"]}
    ).json()
    test = c.get(f"/assessments/{sitting['assessment_id']}", headers=student).json()
    assert test["no_help"] is True, "no hints or tutoring during a timed paper"
    papers = c.get(f"/subjects/{world.subject_id}/past-papers", headers=student).json()
    assert next(p for p in papers if p["paper_ref"] == PAPER)["in_progress"] is True

    first = test["items"][0]["question"]
    answer = {"question_item_id": first["id"], "working": "An answer.", "assessment_id": test["id"]}
    attempt = c.post("/attempts", headers=student, json={**answer, "idempotency_key": f"k-{uuid4().hex}"}).json()
    early = c.post(f"/attempts/{attempt['id']}/evaluate", headers=student)
    assert early.status_code == 409 and early.json()["error"]["code"] == "assessment_not_submitted"

    # All input belongs to the sitting until it is submitted: practice elsewhere is refused.
    outside = {"question_item_id": test["items"][1]["question"]["id"], "working": "Practice."}
    refused = c.post("/attempts", headers=student, json={**outside, "idempotency_key": f"k-{uuid4().hex}"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "assessment_in_progress"

    assert c.post(f"/assessments/{test['id']}/submit", headers=student).status_code == 200
    allowed = c.post("/attempts", headers=student, json={**outside, "idempotency_key": f"k-{uuid4().hex}"})
    assert allowed.status_code == 201


def test_an_abandoned_sitting_stops_locking_everything_else(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, c = auth_headers("test|student"), world.client
    sitting = c.post(
        f"/subjects/{world.subject_id}/sittings", headers=student, json={"paper_ref": PAPER, "questions": ["Q3"]}
    ).json()
    test = c.get(f"/assessments/{sitting['assessment_id']}", headers=student).json()
    outside = {"question_item_id": test["items"][0]["question"]["id"], "working": "Practice."}
    locked = c.post("/attempts", headers=student, json={**outside, "idempotency_key": f"k-{uuid4().hex}"})
    assert locked.status_code == 409

    with world.factory() as s, s.begin():  # started yesterday and never submitted
        set_rls_context(s, user_id=None, role="system")
        row = s.get(Assessment, UUID(sitting["assessment_id"]))
        assert row is not None and row.started_at is not None
        row.started_at = row.started_at - timedelta(hours=13)
    freed = c.post("/attempts", headers=student, json={**outside, "idempotency_key": f"k-{uuid4().hex}"})
    assert freed.status_code == 201, freed.text
    # It is still open, so she can submit it when she is ready.
    assert c.get(f"/sittings/{sitting['assessment_id']}", headers=student).json()["status"] == "in_progress"


def test_an_abandoned_sitting_is_neither_sat_nor_resumed(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, c = auth_headers("test|student"), world.client
    body = {"paper_ref": PAPER, "questions": ["Q2"]}
    first = c.post(f"/subjects/{world.subject_id}/sittings", headers=student, json=body).json()
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        row = s.get(Assessment, UUID(first["assessment_id"]))
        assert row is not None
        row.status = "abandoned"
    paper = next(
        p for p in c.get(f"/subjects/{world.subject_id}/past-papers", headers=student).json() if p["paper_ref"] == PAPER
    )
    assert (paper["assessment_id"], paper["in_progress"], paper["sat_on"]) == (None, False, None)
    again = c.post(f"/subjects/{world.subject_id}/sittings", headers=student, json=body).json()
    assert again["assessment_id"] != first["assessment_id"] and again["status"] == "in_progress"


@pytest.mark.parametrize("questions", [[], ["Q2", "Q3"], ["Q1"], ["Q9"]])
def test_a_sitting_refuses_a_choice_the_paper_does_not_offer(
    world: SimpleNamespace, auth_headers: Auth, questions: list[str]
) -> None:
    refused = world.client.post(
        f"/subjects/{world.subject_id}/sittings",
        headers=auth_headers("test|student"),
        json={"paper_ref": PAPER, "questions": questions},
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "invalid_question_choice"


def test_a_sitting_needs_a_paper_that_exists(world: SimpleNamespace, auth_headers: Auth) -> None:
    refused = world.client.post(
        f"/subjects/{world.subject_id}/sittings",
        headers=auth_headers("test|student"),
        json={"paper_ref": "0495/11/ZZ99", "questions": ["Q2"]},
    )
    assert refused.status_code == 404


def test_a_guardian_cannot_sit_the_paper(world: SimpleNamespace, auth_headers: Auth) -> None:
    refused = world.client.post(
        f"/subjects/{world.subject_id}/sittings?student_id={world.student_id}",
        headers=auth_headers("test|parent"),
        json={"paper_ref": PAPER, "questions": ["Q2"]},
    )
    assert refused.status_code == 403


def test_readiness_is_unknown_for_a_student_with_no_subject(world: SimpleNamespace, auth_headers: Auth) -> None:
    missing = world.client.get(f"/subjects/{uuid4()}/readiness", headers=auth_headers("test|student"))
    assert missing.status_code == 404


def test_a_drill_serves_only_that_command_word(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-R4
    student = auth_headers("test|student")
    session = world.client.post(
        "/tutor/sessions",
        headers=student,
        json={"subject_id": str(world.subject_id), "mode": "practice", "command_word": "Evaluate"},
    )
    assert session.status_code == 201, session.text
    assert session.json()["command_word"] == "evaluate", "however she typed it, the drill is on one word"

    served = []
    for _ in range(3):
        body = world.client.post(f"/tutor/sessions/{session.json()['id']}/next", headers=student).json()
        question = body.get("question")
        if question is None:
            break
        served.append((question["command_word"], question["id"]))

    assert served, "the drill must serve something"
    assert {word for word, _id in served} == {"evaluate"}
    assert len({item_id for _word, item_id in served}) == len(served), "and never the same question twice"


def test_a_drill_on_a_command_word_nothing_uses_is_refused(world: SimpleNamespace, auth_headers: Auth) -> None:
    """Refusing beats opening a drill that says "no questions" on its first turn."""
    refused = world.client.post(
        "/tutor/sessions",
        headers=auth_headers("test|student"),
        json={"subject_id": str(world.subject_id), "mode": "practice", "command_word": "juggle"},
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "no_items_for_command_word"
