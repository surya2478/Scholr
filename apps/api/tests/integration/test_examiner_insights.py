"""Examiner-report insights (AC-R6) through the real API: reached only through a marked answer, most specific
first, and always attributed to the report they came from. Points are fixture text, not from a real report."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import set_rls_context
from app.main import create_app
from app.modules.assessment.models import ExaminerInsight, QuestionItem
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.knowledge.models import Source
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db

Auth = Callable[..., dict[str, str]]
SERIES = "MJ99"  # a series no real report uses, so fixture rows cannot collide with imported ones
TITLE = "Fixture Principal Examiner Report for Teachers, May/June 2099"


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
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
        source = Source(
            tenant_id=w.tenant_id,
            manifest_key=f"fixture-er-{uuid4().hex[:8]}",
            title=TITLE,
            owner="test",
            licence="test fixture",
            authority_tier="A",
            acquired_via="test",
            subject_id=subject_id,
            default_content_kind="examiner_report",
        )
        s.add(source)
        s.flush()

        def item(ref: str) -> Any:
            row = QuestionItem(
                tenant_id=w.tenant_id,
                subject_id=subject_id,
                origin="past_paper",
                source_ref=f"0580/21/{SERIES}/Q{ref}",
                stem="Find the circumference of a circle with radius 2 cm.",
                marks=2,
                command_word="Calculate",
                objective_ids=[objective_id],
                calculator_allowed=True,
                answer_spec={"type": "numeric", "answer": "12.6", "exact": "4*pi", "accuracy": "sf3"},
                mark_scheme={"text": "M1 for 2 x pi x 2\nA1 12.6", "source": "test_fixture"},
                verification_status="verified",
            )
            s.add(row)
            s.flush()
            return row.id

        def insight(question_ref: str | None, kind: str, text: str, ordinal: int = 0) -> None:
            s.add(
                ExaminerInsight(
                    tenant_id=w.tenant_id,
                    source_id=source.id,
                    subject_id=subject_id,
                    syllabus_code="0580",
                    component="21",
                    exam_series=SERIES,
                    report_title=TITLE,
                    question_ref=question_ref,
                    item_ref=f"0580/21/{SERIES}/Q{question_ref}" if question_ref else None,
                    kind=kind,
                    text=text,
                    ordinal=ordinal,
                    pages=[3],
                    segment_key=f"21:{question_ref or 'paper'}",
                    segment_sha="0" * 64,
                    segmenter_version="test",
                    prompt_version="test",
                    model="test",
                )
            )

        target = item("7(a)(ii)")
        other = item("8")
        insight("7(a)(ii)", "common_error", "Used the diameter where the radius was needed.")
        insight("7", "advice", "Show the formula before substituting.")
        insight("8", "advice", "About a different question.")
        insight(None, "advice", "Keep working visible throughout the paper.")
        insight(None, "common_error", "Rounded too early in multi-step questions.", ordinal=1)

    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(settings=get_settings(), session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(**vars(w), target=target, other=other, transport=transport, client=client)


def _marked(world: SimpleNamespace, headers: dict[str, str]) -> str:
    attempt = world.client.post(
        "/attempts",
        headers=headers,
        json={
            "question_item_id": str(world.target),
            "idempotency_key": f"key-{uuid4().hex}",
            "working": "2 x pi x 2",
            "final_answer": "12.6",
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
            "what_went_well": "Method shown.",
            "next_step": "Try arc length.",
            "mistakes": [],
            "confidence": 0.9,
        }
    )
    return world.client.post(f"/attempts/{attempt['id']}/evaluate", headers=headers).json()["id"]


def test_insights_come_with_a_marked_answer_most_specific_first_and_attributed(
    world: SimpleNamespace, auth_headers: Auth
) -> None:
    student = auth_headers("test|student")
    # Serving the question never carries them: the reports name the answers that scored.
    assert "insights" not in str(world.client.get(f"/questions/{world.target}", headers=student).json())

    evaluation_id = _marked(world, student)
    body = world.client.get(f"/evaluations/{evaluation_id}/examiner-insights", headers=student).json()

    assert body["item_ref"] == f"0580/21/{SERIES}/Q7(a)(ii)"
    assert [p["text"] for p in body["question"]] == [
        "Used the diameter where the radius was needed.",
        "Show the formula before substituting.",
    ]
    assert body["question"][0]["attribution"] == f"{TITLE} — Paper 21, Question 7(a)(ii)"
    assert body["question"][1]["attribution"] == f"{TITLE} — Paper 21, Question 7"
    # Whole-paper points: advice first, and never another question's points.
    assert [p["text"] for p in body["paper"]] == [
        "Keep working visible throughout the paper.",
        "Rounded too early in multi-step questions.",
    ]
    assert body["paper"][0]["attribution"] == f"{TITLE} — Paper 21"
    assert "not Scholr's advice" in body["note"]

    parent = auth_headers("test|parent")
    assert world.client.get(f"/evaluations/{evaluation_id}/examiner-insights", headers=parent).status_code == 200


def test_no_evaluation_no_insights(world: SimpleNamespace, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    response = world.client.get(f"/evaluations/{uuid4()}/examiner-insights", headers=student)
    assert response.status_code == 404
