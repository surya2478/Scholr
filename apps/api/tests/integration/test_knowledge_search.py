"""Chunking -> embedding -> hybrid retrieval with a validation state, through the database and the API.

Embeddings come from a deterministic hash embedder (tests/fixtures/llm.py); ranking, tagging and states are real.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.llm.gateway import CallContext
from app.main import create_app
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.knowledge import service as knowledge
from app.modules.knowledge.models import DocumentPage, KnowledgeChunk, KnowledgeDocument, RetrievalLog, Source
from tests.fixtures.llm import hash_embedding, scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]
OFFSET = 1  # PDF page = printed page + 1, as in the Collins scan


@pytest.fixture
def library(household_world: SimpleNamespace) -> SimpleNamespace:
    w = household_world
    starts = sorted((page, code) for code, page in curriculum.objective_start_pages("igcse-maths").items())
    first_page, first_code = starts[0]
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        subject_id = s.scalar(select(Subject.id).where(Subject.code == "igcse-maths"))
        objective_id = curriculum.objectives_by_code(s, subject_id)[first_code][0]

        def add_source(key: str, kind: str, tier: str, pages: list[str]) -> None:
            source = Source(
                tenant_id=w.tenant_id,
                manifest_key=key,
                title=f"Fixture {key}",
                owner="test",
                licence="test fixture",
                authority_tier=tier,
                acquired_via="test",
                subject_id=subject_id,
                default_content_kind=kind,
            )
            s.add(source)
            s.flush()
            doc = KnowledgeDocument(
                tenant_id=w.tenant_id,
                source_id=source.id,
                storage_uri="test://fixture",
                sha256=uuid4().hex,
                content_type="text/markdown",
                page_count=len(pages),
            )
            s.add(doc)
            s.flush()
            for i, text in enumerate(pages):
                s.add(
                    DocumentPage(
                        tenant_id=w.tenant_id,
                        document_id=doc.id,
                        page_number=first_page + OFFSET + i,
                        printed_page_label=str(first_page + i),
                        text=text,
                        extraction_method="test",
                    )
                )

        # Fixture text written for this test (not from any textbook).
        add_source(
            "test-textbook",
            "explanation",
            "B",
            [
                "# Chapter 1\n## Rounding\n"
                "To round to significant figures, count digits from the first non-zero digit.",
                "### Example 1\nRound 0.004567 to 3 significant figures. The first non-zero digit is 4, so 0.00457.",
                "# Answers to Chapter 1\n1 0.00457 2 12300",
            ],
        )
        add_source("test-mark-scheme", "mark_scheme", "A", ["1 0.00457 B1 significant figures"])
    gateway, transport, _ = scripted_gateway()
    transport.embedder = hash_embedding
    return SimpleNamespace(**vars(w), subject_id=subject_id, objective_id=objective_id, gateway=gateway)


def test_chunk_embed_search(library: SimpleNamespace) -> None:
    w = library
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        report = knowledge.chunk_source(s, source_key="test-textbook")
        skipped = knowledge.chunk_source(s, source_key="test-mark-scheme")
    assert report.chunks == 2 and report.tagged == 2 and report.page_offset == OFFSET
    assert len(report.skipped_pages) == 1
    assert skipped.skipped_reason and skipped.chunks == 0

    embedded = knowledge.embed_pending(w.factory, w.gateway, tenant_id=w.tenant_id, model_name="hash")
    assert (embedded.embedded, embedded.remaining) == (2, 0)

    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=w.student_user_id, role="student")
        result = knowledge.search(
            s,
            w.gateway,
            CallContext(request_id="req-search", tenant_id=w.tenant_id, student_id=w.student_id),
            query="round 0.004567 to 3 significant figures",
            subject_id=w.subject_id,
            objective_ids=[w.objective_id],
        )
        assert result.state in {"HIGH", "MEDIUM", "LOW"}
        assert result.chunks[0].content_kind == "worked_example"
        assert all(chunk.aligned for chunk in result.chunks)
        assert all("12300" not in chunk.content for chunk in result.chunks)  # answers section never retrievable
        log = s.get(RetrievalLog, result.log_id)
        assert log is not None and log.student_id == w.student_id and log.state == result.state

    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        kinds = set(s.scalars(select(KnowledgeChunk.content_kind)))
    assert "mark_scheme" not in kinds


def test_search_api_returns_short_excerpts(library: SimpleNamespace, auth_headers: Auth) -> None:
    w = library
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        knowledge.chunk_source(s, source_key="test-textbook")
    knowledge.embed_pending(w.factory, w.gateway, tenant_id=w.tenant_id, model_name="hash")
    client = TestClient(create_app(session_factory=w.factory, gateway=w.gateway))
    resp = client.post(
        "/knowledge/search",
        headers=auth_headers("test|student"),
        json={"query": "significant figures", "subject_id": str(w.subject_id)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] in {"HIGH", "MEDIUM", "LOW", "NONE"}
    assert body["chunks"] and all(len(c["excerpt"]) <= 400 for c in body["chunks"])
