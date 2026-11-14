"""Attempts -> structured_math evaluation -> events -> mastery and mistakes, through the real API and RLS.

The LLM is a scripted transport (tests/fixtures/llm.py); the answer checks, consistency rules and projections are real.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
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
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from tests.fixtures.llm import scripted_gateway, user_prompt

pytestmark = pytest.mark.db

Auth = Callable[..., dict[str, str]]

# Fixture question written for these tests (not from any copyrighted paper).
NUMERIC_SPEC = {"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3", "accept_ranges": []}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


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

        def item(**overrides: Any) -> Any:
            values: dict[str, Any] = {
                "tenant_id": w.tenant_id,
                "subject_id": subject_id,
                "origin": "school",
                "source_ref": f"test/{uuid4().hex[:12]}",
                "stem": "Find the circumference of a circle with radius 2 cm.",
                "marks": 2,
                "command_word": "Calculate",
                "objective_ids": [objective_id],
                "calculator_allowed": True,
                "answer_spec": NUMERIC_SPEC,
                "mark_scheme": {"text": "M1 for 2 x pi x 2\nA1 12.6 or 12.57 or 4pi", "source": "test_fixture"},
                "verification_status": "verified",
            }
            values.update(overrides)
            row = QuestionItem(**values)
            s.add(row)
            s.flush()
            return row.id

        items = {
            "item": item(),
            "reserved": item(reserved_for_study=True),
            "unverified": item(verification_status="unverified"),
        }
    gateway, transport, _ = scripted_gateway()
    settings = get_settings().model_copy(update={"uploads_dir": tmp_path})
    client = TestClient(create_app(settings=settings, session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        **vars(w), **items, objective_id=objective_id, transport=transport, client=client, uploads=tmp_path
    )


def marking(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "awards": [
            {"code": "M1", "awarded": True, "reason": "correct method"},
            {"code": "A1", "awarded": True, "reason": "correct answer"},
        ],
        "marks_awarded": 2,
        "final_answer_correct": True,
        "feedback_summary": "Well done.",
        "what_went_well": "Clear method.",
        "next_step": "Try a question on arc length.",
        "mistakes": [],
        "confidence": 0.9,
    }
    values.update(overrides)
    return values


def submit(world: SimpleNamespace, headers: dict[str, str], **overrides: Any) -> Any:
    body: dict[str, Any] = {
        "question_item_id": str(world.item),
        "idempotency_key": f"key-{uuid4().hex}",
        "working": "2 x pi x 2",
        "final_answer": "12.6",
        "pre_confidence": 3,
    }
    body.update(overrides)
    return world.client.post("/attempts", headers=headers, json=body)


def test_typed_attempt_is_idempotent_and_final_evaluation_updates_mastery(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    question = world.client.get(f"/questions/{world.item}", headers=student).json()
    assert "answer_spec" not in question and "mark_scheme" not in question

    first = submit(world, student, idempotency_key="attempt-key-0001")
    assert first.status_code == 201 and first.json()["status"] == "ready"
    attempt_id = first.json()["id"]
    replay = submit(world, student, idempotency_key="attempt-key-0001")
    assert (replay.status_code, replay.json()["id"]) == (200, attempt_id)
    conflict = submit(world, student, idempotency_key="attempt-key-0001", question_item_id=str(world.unverified))
    assert conflict.json()["error"]["code"] == "idempotency_conflict"

    world.transport.reply(marking())
    evaluation = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()
    assert (evaluation["status"], evaluation["provisional"], evaluation["marks_awarded"]) == ("final", False, 2)
    assert evaluation["final_answer_check"]["status"] == "correct"
    assert evaluation["feedback"]["next_step"]
    assert "status=correct" in user_prompt(world.transport.requests[-1])

    again = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()  # no second LLM call
    assert again["id"] == evaluation["id"]
    assert world.client.get(f"/attempts/{attempt_id}", headers=student).json()["status"] == "evaluated"

    [evidence] = world.client.get(f"/mastery/{world.objective_id}/evidence", headers=student).json()
    assert evidence["evaluation_id"] == evaluation["id"] and evidence["score"] == 1.0
    parent = auth_headers("test|parent")
    assert world.client.get(f"/evaluations/{evaluation['id']}", headers=parent).status_code == 200


def test_tool_llm_disagreement_is_provisional_and_leaves_projections_alone(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    attempt_id = submit(world, student, final_answer="13").json()["id"]  # 2 sf: insufficient accuracy
    world.transport.reply(marking())  # the model wrongly calls it correct
    evaluation = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()
    assert (evaluation["status"], evaluation["provisional"]) == ("needs_review", True)
    assert evaluation["final_answer_check"]["status"] == "insufficient_accuracy"
    # AC-E6: she sees no number and no summary that states one, and is told who checks it.
    assert evaluation["marks_awarded"] is None and evaluation["feedback"]["summary"] == ""
    assert evaluation["awards"] == [] and "parent" in evaluation["pending"]["who"]
    again = world.client.get(f"/evaluations/{evaluation['id']}", headers=student).json()
    assert again["marks_awarded"] is None and again["pending"] is not None
    parent = world.client.get(f"/evaluations/{evaluation['id']}", headers=auth_headers("test|parent")).json()
    assert parent["marks_awarded"] == 2 and parent["pending"] is None  # the reviewer sees the mark to check
    assert world.client.get(f"/mastery/{world.objective_id}/evidence", headers=student).json() == []
    assert world.client.get("/mastery", headers=student).json() == []
    assert world.client.get("/mistakes", headers=student).json() == []


def test_final_evaluation_with_a_mistake_appears_in_the_mistake_bank(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    attempt_id = submit(world, student, final_answer="12.4").json()["id"]
    world.transport.reply(
        marking(
            awards=[
                {"code": "M1", "awarded": True, "reason": "method"},
                {"code": "A1", "awarded": False, "reason": "wrong"},
            ],
            marks_awarded=1,
            final_answer_correct=False,
            mistakes=[
                {
                    "category": "calculation",
                    "label": "premature_rounding",
                    "severity": "medium",
                    "description": "Used 3.1 for pi before multiplying.",
                }
            ],
        )
    )
    evaluation = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()
    assert evaluation["status"] == "final"
    [mistake] = world.client.get("/mistakes", headers=student).json()
    assert mistake["fingerprint"] == "calculation:premature_rounding"
    assert (mistake["status"], mistake["occurrences"], mistake["severity"]) == ("open", 1, "medium")
    # Spaced repair (improvement 8): due the day after it was made, and not closed yet.
    seen = date.fromisoformat(mistake["last_seen"][:10])
    assert mistake["due_on"] == (seen + timedelta(days=1)).isoformat() and mistake["resolved_on"] is None
    assert mistake["description"] == "Used 3.1 for pi before multiplying."
    assert world.client.get("/mistakes", headers=auth_headers("test|parent")).json() == [mistake]


def test_photo_attempt_must_be_confirmed_before_marking(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    world.transport.reply(
        {"working": "$2 \\times \\pi \\times 2$", "final_answer": "12.6", "legibility": "good", "uncertain": []}
    )
    resp = world.client.post(
        "/attempts/photo",
        headers=student,
        data={"question_item_id": str(world.item), "idempotency_key": "photo-key-0001"},
        files=[("photos", ("working.png", PNG, "image/png"))],
    )
    assert resp.status_code == 201, resp.text
    attempt = resp.json()
    assert (attempt["status"], attempt["photo_count"]) == ("awaiting_confirmation", 1)
    assert attempt["transcription"]["final_answer"] == "12.6"
    assert len(list(world.uploads.rglob("*.png"))) == 1

    blocked = world.client.post(f"/attempts/{attempt['id']}/evaluate", headers=student)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "transcription_not_confirmed")

    confirmed = world.client.put(
        f"/attempts/{attempt['id']}/transcription",
        headers=student,
        json={"working": "$2 \\times \\pi \\times 2$", "final_answer": "12.6"},
    ).json()
    assert confirmed["status"] == "ready" and confirmed["transcription"]["edited"] is False

    world.transport.reply(marking())
    assert world.client.post(f"/attempts/{attempt['id']}/evaluate", headers=student).json()["status"] == "final"
    late_edit = world.client.put(
        f"/attempts/{attempt['id']}/transcription", headers=student, json={"working": "x", "final_answer": "99"}
    )
    assert late_edit.json()["error"]["code"] == "already_evaluated"


def test_rejections(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    assert submit(world, student, question_item_id=str(world.unverified)).status_code == 404
    assert submit(world, student, question_item_id=str(world.reserved)).status_code == 404
    assert world.client.get(f"/questions/{world.reserved}", headers=student).status_code == 404
    assert submit(world, parent).status_code == 403
    empty = submit(world, student, working="", final_answer=" ")
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "empty_answer")

    not_image = world.client.post(
        "/attempts/photo",
        headers=student,
        data={"question_item_id": str(world.item), "idempotency_key": "photo-key-0002"},
        files=[("photos", ("working.png", b"not an image at all", "image/png"))],
    )
    assert (not_image.status_code, not_image.json()["error"]["code"]) == (422, "invalid_image")
    assert list(world.uploads.rglob("*.*")) == []


def test_llm_failure_keeps_the_attempt(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    attempt_id = submit(world, student).json()["id"]
    world.transport.fail("quota_exceeded")
    failed = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student)
    assert (failed.status_code, failed.json()["error"]["code"]) == (503, "llm_unavailable")
    assert world.client.get(f"/attempts/{attempt_id}", headers=student).json()["status"] == "ready"


def test_parent_reviews_a_provisional_evaluation(world: SimpleNamespace, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    attempt_id = submit(world, student, final_answer="13").json()["id"]
    world.transport.reply(marking())  # tool/LLM disagreement -> needs_review
    evaluation = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()
    assert evaluation["status"] == "needs_review"

    assert world.client.get("/evaluations/review-queue", headers=student).status_code == 403
    [queued] = world.client.get("/evaluations/review-queue", headers=parent).json()
    assert queued["evaluation"]["id"] == evaluation["id"]
    assert queued["issues"] and "A1" in queued["mark_scheme"] and queued["final_answer"] == "13"

    url = f"/evaluations/{evaluation['id']}/override"
    assert world.client.post(url, headers=student, json={"marks_awarded": 1}).status_code == 403
    too_many = world.client.post(url, headers=parent, json={"marks_awarded": 5})
    assert (too_many.status_code, too_many.json()["error"]["code"]) == (422, "marks_out_of_range")

    done = world.client.post(url, headers=parent, json={"marks_awarded": 1, "note": "method mark only"})
    assert done.status_code == 200, done.text
    body = done.json()
    assert (body["status"], body["provisional"], body["marks_awarded"]) == ("overridden", False, 1)
    assert body["reviewed_at"] is not None
    assert world.client.get("/evaluations/review-queue", headers=parent).json() == []
    assert world.client.post(url, headers=parent, json={"marks_awarded": 2}).status_code == 409

    [evidence] = world.client.get(f"/mastery/{world.objective_id}/evidence", headers=student).json()
    assert evidence["overridden"] is True and evidence["score"] == 0.5


def test_each_mark_says_what_kind_of_mark_it_is(world: SimpleNamespace, auth_headers: Auth) -> None:
    """Improvement 6: her working earned the method mark though the answer was wrong, and the card says so."""
    student = auth_headers("test|student")
    attempt_id = submit(world, student, final_answer="12.4").json()["id"]
    world.transport.reply(
        marking(
            awards=[
                {"code": "M1", "awarded": True, "reason": "2 x pi x 2 seen"},
                {"code": "A1", "awarded": False, "reason": "12.4 is not 12.6"},
            ],
            marks_awarded=1,
            final_answer_correct=False,
        )
    )
    evaluation = world.client.post(f"/attempts/{attempt_id}/evaluate", headers=student).json()
    assert evaluation["status"] == "final"
    method, accuracy = evaluation["awards"]
    assert method["meaning"].startswith("Method mark") and accuracy["meaning"].startswith("Accuracy mark")
    assert "M1" in evaluation["method_note"] and evaluation["skills"] == []
