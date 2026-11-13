"""Tutoring through the real API: sessions, practice selection, help ladder (AC-L1/L2), answer-leak guard, safety
before tutoring, test mode without help (AC-L5), audited guardian reads (AC-S2). The LLM is scripted."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
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
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events.models import LearningEvent
from app.modules.memory.models import LearningMemory
from app.modules.safety.service import load_policy
from app.modules.tutoring.engine import GENERAL_LABEL
from app.modules.tutoring.service import templates
from tests.fixtures.llm import hash_embedding, scripted_gateway, user_prompt

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]

# Fixture question written for these tests.
SPEC = {"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3", "accept_ranges": []}


@pytest.fixture
def world(household_world: SimpleNamespace, tmp_path: Path) -> SimpleNamespace:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        objective_id, subject_id = s.execute(
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
            origin="school",
            source_ref="test/circumference",
            stem="Find the circumference of a circle with radius 2 cm.",
            marks=2,
            command_word="Calculate",
            objective_ids=[objective_id],
            answer_spec=SPEC,
            mark_scheme={"text": "M1 for 2 x pi x 2\nA1 12.6", "source": "test_fixture"},
            verification_status="verified",
        )
        s.add(item)
        s.flush()
        item_id = item.id
    gateway, transport, _ = scripted_gateway()
    transport.embedder = hash_embedding
    settings = get_settings().model_copy(update={"uploads_dir": tmp_path})
    client = TestClient(create_app(settings=settings, session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        **vars(w), subject_id=subject_id, objective_id=objective_id, item_id=item_id, transport=transport, client=client
    )


def tutor_reply(message: str, **overrides: Any) -> dict[str, Any]:
    return {"message": message, "check_question": "What is the radius?", "citations": [], **overrides}


def start(world: SimpleNamespace, headers: dict[str, str], mode: str = "practice") -> str:
    resp = world.client.post(
        "/tutor/sessions", headers=headers, json={"subject_id": str(world.subject_id), "mode": mode}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def event_types(world: SimpleNamespace) -> list[str]:
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        return list(s.scalars(select(LearningEvent.type).order_by(LearningEvent.recorded_at)))


def test_help_ladder_and_answer_leak_guard(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    session_id = start(world, student)
    nxt = world.client.post(f"/tutor/sessions/{session_id}/next", headers=student).json()
    assert nxt["question"]["id"] == str(world.item_id) and "answer_spec" not in nxt["question"]

    first = world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={}).json()
    assert first["kind"] == "ask_for_attempt" and first["reply"]["content"] == templates()["ask_for_attempt"]
    assert world.transport.requests == []  # AC-L1: policy, not the LLM

    world.transport.reply(tutor_reply("Which formula links the radius and the circumference?"))
    second = world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={}).json()
    assert (second["kind"], second["reply"]["assistance_level"], second["session"]["state"]["help_level"]) == (
        "help",
        1,
        1,
    )
    assert "Help level to give: 1" in user_prompt(world.transport.requests[-1])

    attempt = world.client.post(
        "/attempts",
        headers=student,
        json={
            "question_item_id": str(world.item_id),
            "idempotency_key": f"tutor-{uuid4().hex}",
            "final_answer": "12.4",
            "session_id": session_id,
        },
    ).json()
    assert attempt["max_assistance_level"] == 1  # help given in the session is recorded on the attempt
    world.transport.reply(
        {
            "awards": [
                {"code": "M1", "awarded": False, "reason": "x"},
                {"code": "A1", "awarded": False, "reason": "x"},
            ],
            "marks_awarded": 0,
            "final_answer_correct": False,
            "feedback_summary": "Check the formula.",
            "next_step": "Use C = 2πr.",
            "mistakes": [],
            "confidence": 0.9,
        }
    )
    assert world.client.post(f"/attempts/{attempt['id']}/evaluate", headers=student).json()["status"] == "final"

    world.transport.reply(tutor_reply("Use C = 2πr, so the answer is 12.6 cm."))  # leaks the final answer
    third = world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={}).json()
    # Developing band after a miss: floor is a hint (AC-L2). This is the third help request within five minutes,
    # so frustration escalates one level further: a worked example of a similar problem.
    assert third["reply"]["assistance_level"] == 3
    assert third["reply"]["content"] == templates()["reply_withheld"]
    assert third["reply"]["safety_status"] == "withheld"
    assert "0/2 marks" in user_prompt(world.transport.requests[-1])
    assert event_types(world).count("help_given") == 2


def test_safety_runs_before_tutoring(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    session_id = start(world, student)
    world.transport.reply({"category": "self_harm", "severity": 3, "confidence": 0.95, "rationale": "intent"})
    turn = world.client.post(
        f"/tutor/sessions/{session_id}/turns", headers=student, json={"message": "I want to kill myself"}
    ).json()
    assert turn["kind"] == "safety"
    assert turn["reply"]["content"] == load_policy().responses["crisis_response"]
    assert len(world.transport.requests) == 1  # only the safety classifier; no tutor call


def test_explanation_is_labelled_when_ungrounded(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    session_id = start(world, student)
    world.transport.reply({"category": "none", "severity": 0, "confidence": 0.9, "rationale": "study"})
    world.transport.reply(
        tutor_reply("A significant figure is a digit that carries meaning.", uses_general_knowledge=True)
    )
    turn = world.client.post(
        f"/tutor/sessions/{session_id}/turns", headers=student, json={"message": "what is a significant figure?"}
    ).json()
    assert turn["kind"] == "explanation"
    assert turn["reply"]["retrieval_state"] == "NONE"
    assert turn["reply"]["content"].startswith(GENERAL_LABEL)  # no course material: labelled general knowledge
    assert turn["check_question"] == "What is the radius?"


def test_test_mode_gives_no_help(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-L5
    student = auth_headers("test|student")
    session_id = start(world, student, mode="test")
    world.client.post(f"/tutor/sessions/{session_id}/next", headers=student)
    turn = world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={}).json()
    assert turn["kind"] == "notice" and turn["reply"]["content"] == templates()["no_help_in_test"]
    assert world.transport.requests == []


def test_guardian_reads_are_audited_and_only_the_student_can_write(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    session_id = start(world, student)
    world.client.post(f"/tutor/sessions/{session_id}/next", headers=student)
    world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={})
    assert world.client.post(f"/tutor/sessions/{session_id}/help", headers=parent, json={}).status_code == 403
    messages = world.client.get(f"/tutor/sessions/{session_id}/messages", headers=parent).json()
    assert [m["role"] for m in messages] == ["tutor"]
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert "tutoring.conversation_read" in set(s.scalars(select(AuditLog.action)))
    ended = world.client.post(f"/tutor/sessions/{session_id}/end", headers=student).json()
    assert ended["ended_at"] and ended["state"]["phase"] == "ended"
    assert world.client.post(f"/tutor/sessions/{session_id}/next", headers=student).status_code == 409
    assert "session_ended" in event_types(world)


SAFE_CLASSIFIER = {"category": "none", "severity": 0, "confidence": 0.9, "rationale": "study"}


def test_learning_notes_reach_the_tutor_prompts(world: SimpleNamespace, auth_headers: Auth) -> None:
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        s.add(
            LearningMemory(
                tenant_id=world.tenant_id,
                student_id=world.student_id,
                subject_id=world.subject_id,
                kind="misconception",
                statement="Often forgets to double the radius before using the formula.",
                evidence_event_ids=[uuid4()],
                status="active",
            )
        )
    student = auth_headers("test|student")
    session_id = start(world, student)
    world.client.post(f"/tutor/sessions/{session_id}/next", headers=student)
    world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={})  # ask for an attempt: no LLM
    world.transport.reply(tutor_reply("Which formula links the radius and the circumference?"))
    world.client.post(f"/tutor/sessions/{session_id}/help", headers=student, json={})
    assert "Often forgets to double the radius" in user_prompt(world.transport.requests[-1])

    world.transport.reply(SAFE_CLASSIFIER)
    world.transport.reply(tutor_reply("A radius is half a diameter.", uses_general_knowledge=True))
    world.client.post(f"/tutor/sessions/{session_id}/turns", headers=student, json={"message": "what is a radius?"})
    assert "Often forgets to double the radius" in user_prompt(world.transport.requests[-1])


def test_logs_carry_no_conversation_or_answer_text(  # AC-S5
    world: SimpleNamespace, auth_headers: Auth, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    for library in ("sqlalchemy", "httpx", "httpcore"):  # statement and URL logging only; SQL echo is checked below
        caplog.set_level(logging.WARNING, logger=library)
    assert not world.factory.kw["bind"].echo
    marks = ["okapi-question-4471", "narwhal-reply-9021", "quokka-working-5520", "81.4471", "lemur-feedback-3307"]
    student = auth_headers("test|student")
    session_id = start(world, student)

    world.transport.reply(SAFE_CLASSIFIER)
    world.transport.reply(tutor_reply("narwhal-reply-9021 is the idea.", uses_general_knowledge=True))
    turn = world.client.post(
        f"/tutor/sessions/{session_id}/turns", headers=student, json={"message": "what is okapi-question-4471?"}
    )
    assert turn.status_code == 200, turn.text
    world.client.post(f"/tutor/sessions/{session_id}/next", headers=student)
    attempt = world.client.post(
        "/attempts",
        headers=student,
        json={
            "question_item_id": str(world.item_id),
            "idempotency_key": f"logs-{uuid4().hex}",
            "working": "C = 2 x pi x r, quokka-working-5520",
            "final_answer": "81.4471",
            "session_id": session_id,
        },
    ).json()
    world.transport.reply(
        {
            "awards": [
                {"code": "M1", "awarded": False, "reason": "x"},
                {"code": "A1", "awarded": False, "reason": "x"},
            ],
            "marks_awarded": 0,
            "final_answer_correct": False,
            "feedback_summary": "lemur-feedback-3307",
            "next_step": "Use C = 2πr.",
            "mistakes": [],
            "confidence": 0.9,
        }
    )
    assert world.client.post(f"/attempts/{attempt['id']}/evaluate", headers=student).status_code == 200
    world.transport.reply(SAFE_CLASSIFIER)
    world.transport.reply(tutor_reply("Look at the radius again."))
    world.client.post(
        f"/tutor/sessions/{session_id}/help", headers=student, json={"message": "stuck on okapi-question-4471"}
    )

    # The flow may log nothing at all; whatever it does log must not carry the student's or the tutor's text.
    logged = caplog.text + "".join(str(r.args) for r in caplog.records)
    assert [m for m in marks if m in logged] == []


def test_speech_becomes_text_she_checks_and_the_recording_is_not_kept(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    """docs/STUDENT-APP.md §16: her recording goes through the gateway (Flash-Lite, provider preferences, recorded
    in llm_call) and only text comes back. Nothing reaches the Tutor, and no message is stored, until she sends."""
    import base64

    from app.modules.tutoring.models import Message
    from tests.unit.test_speech_input import make_wav

    student = auth_headers("test|student")
    recording = base64.b64encode(make_wav(3)).decode()
    world.transport.reply({"text": "how do I  find the circumference", "unclear": False})
    heard = world.client.post("/tutor/speech", headers=student, json={"audio": recording})
    assert heard.status_code == 200, heard.text
    assert heard.json() == {"text": "how do I find the circumference", "unclear": False}

    [request] = world.transport.requests
    assert request.model == "google/gemini-2.5-flash-lite" and request.provider == {"data_collection": "deny"}
    [audio_part] = [p for p in request.messages[-1]["content"] if p.get("type") == "input_audio"]
    assert audio_part["input_audio"]["format"] == "wav"

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert s.scalars(select(Message)).all() == []  # nothing sent to the Tutor, nothing kept

    # Checked by code before any model call: not base64, not a WAV, silence the model could not hear.
    assert world.client.post("/tutor/speech", headers=student, json={"audio": "%%%"}).status_code == 400
    webm = base64.b64encode(b"\x1aE\xdf\xa3 webm").decode()
    assert world.client.post("/tutor/speech", headers=student, json={"audio": webm}).status_code == 400
    world.transport.reply({"text": "", "unclear": True})
    silent = world.client.post("/tutor/speech", headers=student, json={"audio": recording})
    assert silent.status_code == 422 and silent.json()["error"]["code"] == "nothing_heard"
    assert world.client.post("/tutor/speech", json={"audio": recording}).status_code == 401


def test_a_no_calculator_drill_serves_only_non_calculator_questions(world: SimpleNamespace, auth_headers: Auth) -> None:
    """Improvement 5: Paper 2 practice. The fixture's own item allows a calculator; one non-calculator item is added."""
    student = auth_headers("test|student")
    refused = world.client.post(
        "/tutor/sessions",
        headers=student,
        json={"subject_id": str(world.subject_id), "mode": "practice", "no_calculator": True},
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "no_non_calculator_items")

    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        hand = QuestionItem(
            tenant_id=world.tenant_id,
            subject_id=world.subject_id,
            origin="school",
            source_ref="test/no-calculator",
            stem="Work out $\\frac{3}{4} + \\frac{1}{6}$.",
            marks=2,
            command_word="work out",
            objective_ids=[world.objective_id],
            calculator_allowed=False,
            answer_spec=SPEC,
            mark_scheme={"text": "M1 common denominator\nA1 11/12", "source": "test_fixture"},
            verification_status="verified",
        )
        s.add(hand)
        s.flush()
        hand_id = hand.id

    view = world.client.get(f"/learn/subjects/{world.subject_id}", headers=student).json()
    assert view["non_calculator_questions"] == 1
    created = world.client.post(
        "/tutor/sessions",
        headers=student,
        json={"subject_id": str(world.subject_id), "mode": "practice", "no_calculator": True},
    )
    assert created.status_code == 201 and created.json()["no_calculator"] is True
    served = world.client.post(f"/tutor/sessions/{created.json()['id']}/next", headers=student).json()
    assert served["question"]["id"] == str(hand_id) and served["question"]["calculator_allowed"] is False
    again = world.client.post(f"/tutor/sessions/{created.json()['id']}/next", headers=student).json()
    assert again["question"] is None or again["question"]["id"] == str(hand_id)  # never the calculator item
