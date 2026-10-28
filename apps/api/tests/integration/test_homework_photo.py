"""Photograph your homework, land on the right topic (docs/GO-LIVE-ENGAGEMENT.md F3), end to end.

The reader is scripted (tests/fixtures/llm.py); the chunking, the embeddings' ranking, the retrieval state and
the decision about which topic it is are the real ones.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.knowledge import service as knowledge
from app.modules.knowledge.models import DocumentPage, KnowledgeDocument, RetrievalLog, Source
from tests.fixtures.llm import hash_embedding, scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PAGE = (
    "# Chapter 1\n## Significant figures\n"
    "To round to significant figures, count the digits from the first non-zero digit."
)
# What the scripted reader "sees" on her worksheet: the questions, in her own words, and no answers.
WORKSHEET = "Round 0.004567 to 3 significant figures. Round 12345 to 2 significant figures."


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    starts = sorted((page, code) for code, page in curriculum.objective_start_pages("igcse-maths").items())
    first_page, first_code = starts[0]
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        subject_id = s.scalar(select(Subject.id).where(Subject.code == "igcse-maths"))
        objective_id = curriculum.objectives_by_code(s, subject_id)[first_code][0]
        source = Source(
            tenant_id=w.tenant_id,
            manifest_key="test-textbook",
            title="Fixture textbook",
            owner="test",
            licence="test fixture",
            authority_tier="B",
            acquired_via="test",
            subject_id=subject_id,
            default_content_kind="explanation",
        )
        s.add(source)
        s.flush()
        doc = KnowledgeDocument(
            tenant_id=w.tenant_id,
            source_id=source.id,
            storage_uri="test://fixture",
            sha256=uuid4().hex,
            content_type="text/markdown",
            page_count=1,
        )
        s.add(doc)
        s.flush()
        s.add(
            DocumentPage(
                tenant_id=w.tenant_id,
                document_id=doc.id,
                page_number=first_page + 1,
                printed_page_label=str(first_page),
                text=PAGE,
                extraction_method="test",
            )
        )
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        knowledge.chunk_source(s, source_key="test-textbook")
    gateway, transport, _ = scripted_gateway()
    transport.embedder = hash_embedding
    knowledge.embed_pending(w.factory, gateway, tenant_id=w.tenant_id, model_name="hash")
    client = TestClient(create_app(session_factory=w.factory, gateway=gateway))
    return SimpleNamespace(
        **vars(w), subject_id=subject_id, objective_id=objective_id, transport=transport, client=client
    )


def post(world: SimpleNamespace, headers: dict[str, str], data: bytes = PNG) -> object:
    return world.client.post(
        "/learn/homework-photo",
        headers=headers,
        files={"photo": ("homework.png", data, "image/png")},
    )


def test_a_photo_of_her_homework_offers_the_topic_it_is_on(world: SimpleNamespace, auth_headers: Auth) -> None:
    world.transport.reply({"text": WORKSHEET, "readable": True, "subject_words": ["Mathematics"]})
    body = post(world, auth_headers("test|student")).json()

    assert body["read"] is True and body["state"] in {"HIGH", "MEDIUM"}
    assert body["notice"] is None
    assert str(world.objective_id) in [m["objective_id"] for m in body["matches"]]
    match = next(m for m in body["matches"] if m["objective_id"] == str(world.objective_id))
    assert match["code"] and match["statement"] and match["subject_name"] == "Mathematics"

    # She is shown a short look at what was read, and a topic — never a line of the book behind the match.
    assert body["text_preview"].startswith("Round 0.004567")
    assert "count the digits" not in str(body)

    # Nothing of her worksheet is kept: no retrieval log row, and no table holds the text.
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert s.scalar(select(func.count()).select_from(RetrievalLog)) == 0


def test_an_unreadable_photo_says_so_and_offers_nothing(world: SimpleNamespace, auth_headers: Auth) -> None:
    world.transport.reply({"text": "", "readable": False, "subject_words": []})
    body = post(world, auth_headers("test|student")).json()
    assert body["read"] is False and body["matches"] == [] and body["state"] == "NONE"
    assert body["notice"] and "couldn't read" in body["notice"]


def test_a_page_her_books_do_not_cover_tells_her_to_choose_herself(world: SimpleNamespace, auth_headers: Auth) -> None:
    world.transport.reply(
        {"text": "Explain the causes of the French Revolution in 1789.", "readable": True, "subject_words": []}
    )
    body = post(world, auth_headers("test|student")).json()
    assert body["read"] is True and body["matches"] == []
    assert body["notice"] and "pick the topic yourself" in body["notice"]


def test_a_file_that_is_not_an_image_is_refused_with_no_model_call(world: SimpleNamespace, auth_headers: Auth) -> None:
    # The script is empty: the scripted transport fails the test if anything calls a model, which is the point.
    response = post(world, auth_headers("test|student"), data=b"%PDF-1.7 this is not a photo")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_image"
    assert world.transport.requests == []


def test_only_a_student_can_send_her_homework(world: SimpleNamespace, auth_headers: Auth) -> None:
    assert post(world, auth_headers("test|parent")).status_code == 403
    assert world.transport.requests == []
