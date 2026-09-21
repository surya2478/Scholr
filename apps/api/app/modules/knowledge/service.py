"""Knowledge service: chunk extracted pages, embed chunks, and grounded hybrid retrieval.

Public functions used by other modules: ``search`` (tutoring), ``chunk_source`` / ``embed_pending`` (jobs).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import set_rls_context
from app.llm.gateway import CallContext, LLMGateway
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.knowledge.chunking import PageText, chunk_pages, page_offset, printed_page_map, section_for_page
from app.modules.knowledge.models import DocumentPage, KnowledgeChunk, KnowledgeDocument, RetrievalLog, Source
from app.modules.knowledge.ranking import (
    ALIGNMENT_BONUS,
    Candidate,
    StateThresholds,
    reciprocal_rank_fusion,
    retrieval_state,
)
from app.modules.subjects import service as subjects

# Phase 1: questions and mark schemes are served through question_item only, never retrieved as text,
# so retrieval cannot leak answers (including items reserved for the validation study).
NOT_RETRIEVABLE_KINDS = frozenset({"question", "mark_scheme"})
CANDIDATES_PER_RANKING = 30
EXCERPT_CHARS = 400


# ---------------------------------------------------------------------------
# Chunking and embedding
# ---------------------------------------------------------------------------


@dataclass
class ChunkReport:
    source_key: str
    chunks: int = 0
    tagged: int = 0
    skipped_pages: list[int] = field(default_factory=list)
    page_offset: int | None = None
    skipped_reason: str | None = None
    reused_embeddings: int = 0


def chunk_source(s: Session, *, source_key: str) -> ChunkReport:
    """(Re)build the chunks of every document of a source from its stored pages. Idempotent."""
    report = ChunkReport(source_key)
    source = s.scalar(select(Source).where(Source.manifest_key == source_key))
    if source is None:
        raise ValueError(f"unknown source: {source_key}")
    if source.default_content_kind in NOT_RETRIEVABLE_KINDS:
        report.skipped_reason = f"{source.default_content_kind} sources are not retrievable in Phase 1"
        return report

    subject_code = None
    starts: list[tuple[int, tuple[UUID, UUID]]] = []
    if source.subject_id is not None:
        subject_code = curriculum.subject_summaries(s, [source.subject_id])[source.subject_id].code
        by_code = curriculum.objectives_by_code(s, source.subject_id)
        if source.authority_tier in ("B", "C"):  # page-based tagging applies to the course textbook(s)
            starts = sorted(
                (page, by_code[code])
                for page, code in curriculum.objective_section_starts(subject_code)
                if code in by_code
            )

    default_kind = source.default_content_kind
    for document in s.scalars(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source.id)):
        rows = s.execute(
            select(DocumentPage.page_number, DocumentPage.text, DocumentPage.printed_page_label).where(
                DocumentPage.document_id == document.id
            )
        ).all()
        labels = [(r.page_number, r.printed_page_label) for r in rows]
        report.page_offset = page_offset(labels)
        printed = printed_page_map(labels)
        drafts, skipped = chunk_pages([PageText(r.page_number, r.text) for r in rows], default_kind)
        report.skipped_pages.extend(sorted(skipped))
        # Keep embeddings of chunks whose text is unchanged, so re-chunking or re-tagging costs nothing.
        previous = {
            content: (embedding, model)
            for content, embedding, model in s.execute(
                select(KnowledgeChunk.content, KnowledgeChunk.embedding, KnowledgeChunk.embedding_model).where(
                    KnowledgeChunk.document_id == document.id, KnowledgeChunk.embedding.is_not(None)
                )
            )
        }
        s.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        for draft in drafts:
            printed_start = printed.get(draft.page_start)
            printed_end = printed.get(draft.page_end)
            embedding, embedding_model = previous.get(draft.content, (None, None))
            report.reused_embeddings += embedding is not None
            section = section_for_page(printed_start, starts) if (printed_start is not None and starts) else None
            s.add(
                KnowledgeChunk(
                    tenant_id=source.tenant_id,
                    document_id=document.id,
                    subject_id=source.subject_id,
                    topic_id=section[1] if section else None,
                    objective_ids=[section[0]] if section else [],
                    content_kind=draft.content_kind,
                    authority_tier=source.authority_tier,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    heading_path=draft.heading_path,
                    content=draft.content,
                    embedding=embedding,
                    embedding_model=embedding_model,
                    meta={"printed_page_start": printed_start, "printed_page_end": printed_end, "chunker": "v1"},
                )
            )
            report.chunks += 1
            report.tagged += section is not None
    source.ingestion_status = "chunked"
    s.flush()
    audit.record(
        s,
        tenant_id=source.tenant_id,
        actor_user_id=None,
        actor_role="system",
        action="knowledge.chunked",
        entity_type="source",
        entity_id=source.id,
        meta={"chunks": report.chunks, "tagged": report.tagged, "skipped_pages": len(report.skipped_pages)},
    )
    return report


@dataclass
class EmbedReport:
    embedded: int = 0
    remaining: int = 0


def embed_pending(
    session_factory: sessionmaker[Session],
    gateway: LLMGateway,
    *,
    tenant_id: UUID,
    source_key: str | None = None,
    batch_size: int = 64,
    model_name: str = "",
) -> EmbedReport:
    """Embed chunks that have no embedding yet, committing batch by batch (resumable)."""
    report = EmbedReport()
    ctx = CallContext(request_id=f"embed:{source_key or 'all'}", tenant_id=tenant_id)

    def pending_query():  # noqa: ANN202
        query = select(KnowledgeChunk).where(KnowledgeChunk.embedding.is_(None))
        if source_key:
            query = (
                query.join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .join(Source, Source.id == KnowledgeDocument.source_id)
                .where(Source.manifest_key == source_key)
            )
        return query

    while True:
        with session_factory() as s, s.begin():
            set_rls_context(s, user_id=None, role="system")
            batch = s.scalars(pending_query().order_by(KnowledgeChunk.id).limit(batch_size)).all()
            if not batch:
                break
            texts = [f"{c.heading_path}\n{c.content}" if c.heading_path else c.content for c in batch]
            vectors = gateway.embed(texts, ctx)
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
                chunk.embedding_model = model_name
            report.embedded += len(batch)
    with session_factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        report.remaining = s.scalar(select(func.count()).select_from(pending_query().subquery())) or 0
        if source_key and report.remaining == 0:
            source = s.scalar(select(Source).where(Source.manifest_key == source_key))
            if source is not None:
                source.ingestion_status = "embedded"
                source.ingested_at = datetime.now(UTC)
    return report


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievedChunk:
    id: UUID
    source_title: str
    printed_page: int | None
    heading_path: str | None
    content_kind: str
    authority_tier: str
    content: str
    similarity: float | None
    aligned: bool
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    state: str
    chunks: list[RetrievedChunk]
    log_id: UUID | None


def search(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    query: str,
    subject_id: UUID,
    objective_ids: Sequence[UUID] = (),
    k: int | None = None,
) -> RetrievalResult:
    """Hybrid retrieval within one subject (never across subjects in Phase 1), with a validation state."""
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        raise ValueError("unknown subject")
    config = subjects.explained_config_for(subject.code).retrieval  # taught or lessons-only
    top_k = k or config.top_k
    wanted = set(objective_ids)
    filters = (
        KnowledgeChunk.subject_id == subject_id,
        KnowledgeChunk.authority_tier.in_(config.allowed_authority_tiers),
        KnowledgeChunk.content_kind.not_in(NOT_RETRIEVABLE_KINDS),
    )

    vector = gateway.embed([query], ctx)[0]
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    vector_rows = s.execute(
        select(KnowledgeChunk.id, distance.label("distance"))
        .where(*filters, KnowledgeChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(CANDIDATES_PER_RANKING)
    ).all()
    ts_query = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(KnowledgeChunk.tsv, ts_query)
    keyword_rows = s.execute(
        select(KnowledgeChunk.id, rank.label("rank"))
        .where(*filters, KnowledgeChunk.tsv.op("@@")(ts_query))
        .order_by(rank.desc())
        .limit(CANDIDATES_PER_RANKING)
    ).all()

    similarity = {row.id: 1.0 - float(row.distance) for row in vector_rows}
    keyword_ids = {row.id for row in keyword_rows}
    fused = reciprocal_rank_fusion([[r.id for r in vector_rows], [r.id for r in keyword_rows]])
    ids = list(fused)
    rows = (
        {
            row.KnowledgeChunk.id: row
            for row in s.execute(
                select(KnowledgeChunk, Source.title)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .join(Source, Source.id == KnowledgeDocument.source_id)
                .where(KnowledgeChunk.id.in_(ids))
            )
        }
        if ids
        else {}
    )

    def aligned(chunk: KnowledgeChunk) -> bool:
        return bool(wanted) and bool(wanted.intersection(chunk.objective_ids or []))

    for chunk_id in ids:
        if chunk_id in rows and aligned(rows[chunk_id].KnowledgeChunk):
            fused[chunk_id] += ALIGNMENT_BONUS
    ranked = [cid for cid in sorted(ids, key=lambda cid: fused[cid], reverse=True) if cid in rows][:top_k]

    chunks = [
        RetrievedChunk(
            id=cid,
            source_title=rows[cid].title,
            printed_page=(rows[cid].KnowledgeChunk.meta or {}).get("printed_page_start"),
            heading_path=rows[cid].KnowledgeChunk.heading_path,
            content_kind=rows[cid].KnowledgeChunk.content_kind,
            authority_tier=rows[cid].KnowledgeChunk.authority_tier,
            content=rows[cid].KnowledgeChunk.content,
            similarity=round(similarity[cid], 4) if cid in similarity else None,
            aligned=aligned(rows[cid].KnowledgeChunk),
            score=round(fused[cid], 6),
        )
        for cid in ranked
    ]
    thresholds = StateThresholds(
        high=config.state_thresholds.high, medium=config.state_thresholds.medium, low=config.state_thresholds.low
    )
    state = retrieval_state(
        [Candidate(c.similarity, c.id in keyword_ids, c.aligned, c.authority_tier) for c in chunks],
        objective_scoped=bool(wanted),
        thresholds=thresholds,
    )
    log = RetrievalLog(
        tenant_id=ctx.tenant_id,
        student_id=ctx.student_id,
        request_id=ctx.request_id,
        query=query,
        filters={
            "subject_id": str(subject_id),
            "objective_ids": [str(o) for o in wanted],
            "tiers": list(config.allowed_authority_tiers),
        },
        candidates=[
            {"chunk_id": str(c.id), "similarity": c.similarity, "score": c.score, "aligned": c.aligned} for c in chunks
        ],
        state=state,
        top_score=chunks[0].similarity if chunks else None,
        created_at=datetime.now(UTC),
    )
    s.add(log)
    s.flush()
    return RetrievalResult(state=state, chunks=chunks, log_id=log.id)


def chunk_texts(s: Session, chunk_ids: Sequence[UUID]) -> dict[UUID, str]:
    """chunk_id -> content, for re-checking something written from those chunks (lessons, AC-U4)."""
    if not chunk_ids:
        return {}
    return dict(
        s.execute(select(KnowledgeChunk.id, KnowledgeChunk.content).where(KnowledgeChunk.id.in_(chunk_ids))).all()
    )  # type: ignore[arg-type]
