"""Learn: streams, subjects, topic pages and lessons through the real API and RLS (docs/STUDENT-APP.md).

The LLM is the scripted transport (tests/fixtures/llm.py). Retrieval is replaced with a fixed result so the lesson
guard sees known excerpts; the excerpts and question stems are fixture text written for these tests.
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

from app.core.config import API_ROOT, get_settings
from app.core.db import set_rls_context
from app.llm.gateway import CallContext
from app.main import create_app
from app.modules.assessment.models import QuestionItem
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events.models import LearningEvent
from app.modules.knowledge import service as knowledge
from app.modules.learn import service as learn
from app.seed.curriculum import load_file, seed_curriculum
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db

Auth = Callable[..., dict[str, str]]
EXCERPT = (
    "Fixture excerpt: a factor divides a whole number exactly, and factors are found in pairs whose product "
    "is the number itself."
)


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
            .limit(2)
        ).all()
        (objective, subject_id), (other, _) = rows

        def item(**overrides: Any) -> Any:
            values: dict[str, Any] = {
                "tenant_id": w.tenant_id,
                "subject_id": subject_id,
                "origin": "school",
                "source_ref": f"test/{uuid4().hex[:12]}",
                "stem": "Fixture: list the factors of 12.",
                "marks": 2,
                "command_word": "list",
                "objective_ids": [objective],
                "answer_spec": {"type": "set_of_values", "answer": "1, 2, 3, 4, 6, 12"},
                "mark_scheme": {"text": "B2 all six", "source": "test_fixture"},
                "verification_status": "verified",
            }
            values.update(overrides)
            row = QuestionItem(**values)
            s.add(row)
            s.flush()
            return row.id

        items = {
            "school": item(),
            "past": item(origin="past_paper", source_ref="0580/21/MJ99/Q3", marks=3),
            "reserved": item(reserved_for_study=True),
            "unverified": item(verification_status="unverified"),
        }
    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(settings=get_settings(), session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        **vars(w),
        **items,
        objective=str(objective),
        objective_uuid=objective,
        other=str(other),
        subject_id=str(subject_id),
        gateway=gateway,
        transport=transport,
        client=client,
    )


def fixed_retrieval(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    chunk = knowledge.RetrievedChunk(
        id=uuid4(),
        source_title="Fixture Maths Book",
        printed_page=13,
        heading_path="Factors",
        content_kind="explanation",
        authority_tier="B",
        content=EXCERPT,
        similarity=0.8,
        aligned=True,
        score=1.0,
    )

    def search(*_: Any, **__: Any) -> knowledge.RetrievalResult:
        return knowledge.RetrievalResult(state=state, chunks=[chunk] if state != "NONE" else [], log_id=None)

    monkeypatch.setattr(knowledge, "search", search)


DRAFT = {
    "summary": "Factors divide a number exactly and come in pairs.",
    "sections": [
        {
            "heading": "Pairs",
            "body": "Each factor has a partner; multiply them and you get the number.",
            "sources": [1],
        },
        {"heading": "Uncited", "body": "A claim with nothing behind it.", "sources": []},
    ],
    "key_terms": [{"term": "Factor", "meaning": "A whole number that divides another exactly.", "sources": [1]}],
    "worked_examples": [
        {
            "problem": "Largest factor of 150 below 100.",
            "steps": ["150 = 2 x 75"],
            "final_answer": "75",
            "answer_expression": "150/2",
            "sources": [1],
        },
        {
            "problem": "Same with an arithmetic slip.",
            "steps": ["150 = 2 x 70"],
            "final_answer": "70",
            "answer_expression": "150/2",
            "sources": [1],
        },
    ],
    "pitfalls": ["Forgetting 1 and the number itself."],
}


def find_objective(chapters: list[dict], objective_id: str) -> dict | None:
    for chapter in chapters:
        for o in chapter["objectives"]:
            if o["id"] == objective_id:
                return o
        found = find_objective(chapter["chapters"], objective_id)
        if found:
            return found
    return None


def test_streams_and_subject_come_from_config_and_never_show_a_confident_zero(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    streams = {s["key"]: s for s in world.client.get("/learn/streams", headers=student).json()}
    assert streams["INDIA"]["status"] == "later" and streams["INDIA"]["subjects"] == []
    [maths] = [s for s in streams["IGCSE"]["subjects"] if s["code"] == "igcse-maths"]
    assert maths["stage"] == "taught" and maths["objectives"] > 0
    assert maths["secure"] is None and maths["practised"] == 0  # no evidence: not "0 secure"

    view = world.client.get(f"/learn/subjects/{world.subject_id}", headers=student).json()
    card = find_objective(view["chapters"], world.objective)
    assert card is not None
    assert (card["items"], card["lesson"], card["mastery_level"]) == (2, "none", None)


def test_topic_page_serves_only_verified_unreserved_items(world: SimpleNamespace, auth_headers: Auth) -> None:
    topic = world.client.get(f"/learn/objectives/{world.objective}", headers=auth_headers("test|student")).json()
    assert topic["lesson_available"] and topic["lesson"] is None
    assert [i["id"] for i in topic["check_yourself"]] == [str(world.school)]
    assert [i["id"] for i in topic["exam_questions"]] == [str(world.past)]
    served = {i["id"] for i in topic["check_yourself"] + topic["exam_questions"]}
    assert str(world.reserved) not in served and str(world.unverified) not in served


def test_a_lesson_is_written_once_guarded_and_audited(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_retrieval(monkeypatch, "HIGH")
    student = auth_headers("test|student")
    world.transport.reply(DRAFT)
    lesson = world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=student).json()

    assert lesson["status"] == "ready"
    assert [s["heading"] for s in lesson["sections"]] == ["Pairs"]
    assert lesson["sections"][0]["sources"] == [{"title": "Fixture Maths Book", "page": 13}]
    # Maths asks for SymPy checking: the example with the slip never reaches her.
    assert [(e["final_answer"], e["checked"]) for e in lesson["worked_examples"]] == [("75", "sympy")]

    again = world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=student).json()
    assert again["id"] == lesson["id"] and len(world.transport.requests) == 1  # stored, not rewritten
    topic = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    assert topic["lesson"]["id"] == lesson["id"] and topic["objective"]["lesson"] == "ready"
    # What the page is made of (AC-U13): computed from the page's own content, nothing done yet.
    assert [x["key"] for x in topic["steps"]][0] == "lesson"
    assert not any(x["done"] for x in topic["steps"])
    assert topic["minutes"] == sum(x["minutes"] for x in topic["steps"]) >= len(topic["steps"])

    world.client.post(f"/learn/objectives/{world.objective}/read", headers=student)
    read = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    assert read["steps"][0]["done"] is True  # her own record, so it still says so tomorrow

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        [meta] = s.scalars(select(AuditLog.meta).where(AuditLog.action == "learn.lesson_written")).all()
    assert meta["status"] == "ready" and meta["prompt_version"] == learn.LESSON_PROMPT_VERSION


def test_thin_material_means_no_lesson_and_no_model_call(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_retrieval(monkeypatch, "LOW")
    lesson = world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=auth_headers("test|student"))
    assert lesson.json()["status"] == "not_enough_material"
    assert world.transport.requests == []


def test_reading_a_lesson_introduces_the_topic_and_a_parent_reading_does_not(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_retrieval(monkeypatch, "HIGH")
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    world.transport.reply(DRAFT)
    world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=student)

    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=parent).status_code == 204
    assert world.client.get("/mastery", headers=student).json() == []
    assert world.client.post(f"/learn/objectives/{world.objective}/read", headers=student).status_code == 204
    [row] = world.client.get("/mastery", headers=student).json()
    assert (row["objective_id"], row["level"], row["level_name"]) == (world.objective, 1, "Introduced")


def test_a_control_topic_is_school_led_until_crossover(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    pair = {
        "subject_id": world.subject_id,
        "pair_code": "L1",
        "app_objective_ids": [world.other],
        "control_objective_ids": [world.objective],
        "assignment_method": "coin flip recorded by parent",
    }
    assert world.client.post("/studies/assignments", headers=parent, json=pair).status_code == 201

    topic = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    assert topic["objective"]["school_led"] and not topic["lesson_available"]
    assert topic["check_yourself"] == [] and topic["exam_questions"] == []
    assert "app" not in topic["notice"] and "control" not in topic["notice"]  # no arm labels for her
    refused = world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=student)
    assert refused.status_code == 409 and world.transport.requests == []


def test_a_lessons_only_subject_explains_and_never_sets_marks_or_tutors(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage `lessons` (docs/STUDENT-APP.md D4): Physics gets grounded lessons and nothing else yet."""
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_curriculum(s, load_file(API_ROOT.parents[1] / "content" / "curriculum" / "igcse-physics-0625.yaml"))
        density, physics = s.execute(
            select(LearningObjective.id, Topic.subject_id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-physics", LearningObjective.code == "1.4")
        ).one()
    student = auth_headers("test|student")

    topic = world.client.get(f"/learn/objectives/{density}", headers=student).json()
    assert topic["subject"]["stage"] == "lessons"
    # Lessons-only means no questions and no marking — but the Tutor answers doubts (D4, amended 20 Sep 2026).
    assert topic["lesson_available"] is True and topic["tutor_available"] is True
    assert topic["check_yourself"] == [] and topic["exam_questions"] == []
    assert "doesn't set or mark" in topic["notice"]

    fixed_retrieval(monkeypatch, "HIGH")
    # Physics answers carry units (subject config `answer_units`): the one without a unit is dropped, and the
    # one with a unit keeps the value and the unit apart — SymPy checks the number, Pint the unit.
    with_units = {
        **DRAFT,
        "worked_examples": [
            {**DRAFT["worked_examples"][0], "unit": "kg/m^3"},
            {**DRAFT["worked_examples"][0], "unit": "bananas"},
        ],
    }
    world.transport.reply(with_units)
    lesson = world.client.post(f"/learn/objectives/{density}/lesson", headers=student).json()
    assert lesson["status"] == "ready"
    assert [(e["final_answer"], e["unit"], e["checked"]) for e in lesson["worked_examples"]] == [
        ("75", "kg/m³", "sympy")
    ]

    doubt = world.client.post("/tutor/sessions", headers=student, json={"subject_id": str(physics), "mode": "learn"})
    assert doubt.status_code == 201, doubt.text
    # ...but practice and tests still need a taught subject: there is nothing here to set or mark.
    for mode in ("practice", "test"):
        refused = world.client.post("/tutor/sessions", headers=student, json={"subject_id": str(physics), "mode": mode})
        assert refused.status_code == 409 and refused.json()["error"]["code"] == "subject_not_taught"


WALKTHROUGH = {
    "steps": [
        {"text": "Pair the factors: $1 \times 12 = 12$, $2 \times 6 = 12$, $3 \times 4 = 12$.", "mark": ""},
        {"text": "List every number from the pairs, smallest first.", "mark": "B2"},
    ],
    "final_answer": "1, 2, 3, 4, 6, 12",
    "tip": "Missing 1 or the number itself loses the mark.",
}


def test_the_exam_level_counts_the_papers_and_shows_a_solved_question_only_once_approved(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-U16: how the topic is examined comes from the bank; a solved past-paper question is written from its mark
    scheme, checked by code, and reaches her only after a person approves it — and is then not offered to try."""
    student = auth_headers("test|student")
    fixed_retrieval(monkeypatch, "HIGH")
    world.transport.reply(DRAFT)
    world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=student)

    topic = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    level = topic["exam_level"]
    assert level["solves"] is True and level["worked"] is None
    assert level["how_examined"] == {
        "asked": 1,
        "marks_min": 3,
        "marks_max": 3,
        "papers": ["Paper 2"],
        "years": ["2099"],
        "command_words": ["list"],
    }
    before = next(x["minutes"] for x in topic["steps"] if x["key"] == "lesson")

    ctx = CallContext(request_id="test-walkthrough", tenant_id=world.tenant_id)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        prepared = learn.prepare_walkthrough(s, world.objective_uuid)
    assert prepared is not None and prepared.item.id == str(world.past)
    wrong = {**WALKTHROUGH, "final_answer": "1, 2, 3, 4, 12"}
    world.transport.reply(wrong)
    assert learn.write_walkthrough(world.gateway, ctx, prepared).content is None  # the answer is not the scheme's
    world.transport.reply(WALKTHROUGH)
    written = learn.write_walkthrough(world.gateway, ctx, prepared)
    assert written.content is not None and written.checks["marks_named"] == ["B2"]
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert learn.record_walkthrough(s, world.objective_uuid, written, actor=None, now=datetime.now(UTC))

    waiting = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    assert waiting["exam_level"]["worked"] is None  # nobody has read it yet
    assert [i["id"] for i in waiting["exam_questions"]] == [str(world.past)]

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert learn.decide_walkthrough(s, world.objective_uuid, approved=True, actor=None)
    shown = world.client.get(f"/learn/objectives/{world.objective}", headers=student).json()
    worked = shown["exam_level"]["worked"]
    assert worked["item_id"] == str(world.past) and worked["label"] == "June 2099 · Paper 21 · Q3"
    assert [x["mark"] for x in worked["steps"]] == ["", "B2"] and worked["final_answer"] == "1, 2, 3, 4, 6, 12"
    assert shown["exam_questions"] == []  # solved on the page, so not offered as one to try
    after = next(x["minutes"] for x in shown["steps"] if x["key"] == "lesson")
    assert after == before + 3  # about a minute a mark

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        actions = s.scalars(select(AuditLog.action).where(AuditLog.action.like("learn.exam_walkthrough%"))).all()
    assert sorted(actions) == ["learn.exam_walkthrough_approved", "learn.exam_walkthrough_written"]


def test_rewriting_a_lesson_keeps_its_solved_exam_question(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_retrieval(monkeypatch, "HIGH")
    world.transport.reply(DRAFT)
    world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=auth_headers("test|student"))
    ctx = CallContext(request_id="test-rewrite", tenant_id=world.tenant_id)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        prepared = learn.prepare_walkthrough(s, world.objective_uuid)
    assert prepared is not None
    world.transport.reply(WALKTHROUGH)
    written = learn.write_walkthrough(world.gateway, ctx, prepared)
    world.transport.reply(DRAFT)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        learn.record_walkthrough(s, world.objective_uuid, written, actor=None, now=datetime.now(UTC))
        lesson_prep = learn.prepare_lesson(s, world.gateway, ctx, world.objective_uuid, rewrite=True)
    assert isinstance(lesson_prep, learn.PreparedLesson)
    rewritten = learn.write_lesson(world.gateway, ctx, lesson_prep)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        row = learn.record_lesson(s, lesson_prep, rewritten, actor=None, now=datetime.now(UTC))
        assert row.content["exam"]["final_answer"] == "1, 2, 3, 4, 6, 12"
        assert row.content["sections"][0]["heading"] == "Pairs"


SAFE = {"category": "none", "severity": 0, "confidence": 0.9, "rationale": "study"}


def test_the_viva_judges_each_step_against_the_approved_walkthrough_and_records_no_mark(
    world: SimpleNamespace, auth_headers: Auth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/STUDENT-APP.md §19: only an approved walkthrough can be defended; a verdict is checked in code, recorded
    as her self-explanation (not a mark), and a parent cannot answer for her."""
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    fixed_retrieval(monkeypatch, "HIGH")
    world.transport.reply(DRAFT)
    world.client.post(f"/learn/objectives/{world.objective}/lesson", headers=student)
    ctx = CallContext(request_id="test-viva", tenant_id=world.tenant_id)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        prepared = learn.prepare_walkthrough(s, world.objective_uuid)
    assert prepared is not None
    world.transport.reply(WALKTHROUGH)
    written = learn.write_walkthrough(world.gateway, ctx, prepared)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        learn.record_walkthrough(s, world.objective_uuid, written, actor=None, now=datetime.now(UTC))

    # Not approved yet: nothing to defend.
    assert world.client.get(f"/learn/viva?subject_id={world.subject_id}", headers=student).json() == []
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        learn.decide_walkthrough(s, world.objective_uuid, approved=True, actor=None)
    [topic] = world.client.get(f"/learn/viva?subject_id={world.subject_id}", headers=student).json()
    assert (topic["objective_id"], topic["steps"], topic["marks"]) == (world.objective, 2, 3)
    question = world.client.get(f"/learn/viva/{world.objective}", headers=student).json()
    assert "steps" in question and "step_text" not in question  # the solution is not sent with the question

    step1 = f"/learn/viva/{world.objective}/steps/1"
    world.transport.reply(SAFE)
    world.transport.reply({"verdict": "right", "what_was_right": "Pairing works.", "missing": "", "hint": ""})
    out = world.client.post(
        step1, headers=student, json={"explanation": "I pair factors that multiply to 12, like 3 and 4"}
    )
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["verdict"] == "right" and body["step_text"].startswith("Pair the factors") and body["last"] is False
    # A one-word answer is "not yet", whatever the model says.
    world.transport.reply(SAFE)
    world.transport.reply({"verdict": "right", "what_was_right": "Great!", "missing": "", "hint": ""})
    assert world.client.post(step1, headers=student, json={"explanation": "pairs"}).json()["verdict"] == "not_yet"

    assert world.client.post(step1, headers=parent, json={"explanation": "she would pair them"}).status_code == 403
    assert (
        world.client.post(
            f"/learn/viva/{world.objective}/steps/9", headers=student, json={"explanation": "x y z"}
        ).status_code
        == 404
    )

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        rows = s.execute(
            select(LearningEvent.type, LearningEvent.payload).where(LearningEvent.type == "self_explanation_given")
        ).all()
    assert [r.payload["verdict"] for r in rows] == ["right", "not_yet"]
    assert all("explanation" not in r.payload for r in rows)  # her words are not kept in the event
    assert world.client.get("/mastery", headers=student).json() == []  # a verdict is not a mark
