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
from app.modules.knowledge.chunking import PageText, chunk_pages, page_offset, printed_page_map, sections_for_span
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
            sections = (
                sections_for_span(printed_start, printed_end or printed_start, starts)
                if (printed_start is not None and starts)
                else []
            )
            section = sections[0] if sections else None
            s.add(
                KnowledgeChunk(
                    tenant_id=source.tenant_id,
                    document_id=document.id,
                    subject_id=source.subject_id,
                    topic_id=section[1] if section else None,
                    objective_ids=list(dict.fromkeys(s_[0] for s_ in sections)),
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

    # The objective's own chunks, ranked by the same vector distance. Across a whole book the nearest chunks can all
    # be chapter summaries and question pages, so the pages a topic is actually taught on were found only by
    # keyword and carried no similarity (Biology 1.1 and 4.1, Chemistry 3.1, 22 Sep 2026). They are still held to
    # the same thresholds below; this only makes sure they are measured.
    aligned_rows = (
        s.execute(
            select(KnowledgeChunk.id, distance.label("distance"))
            .where(*filters, KnowledgeChunk.embedding.is_not(None), KnowledgeChunk.objective_ids.overlap(list(wanted)))
            .order_by(distance)
            .limit(CANDIDATES_PER_RANKING)
        ).all()
        if wanted
        else []
    )
    similarity = {row.id: 1.0 - float(row.distance) for row in (*vector_rows, *aligned_rows)}
    keyword_ids = {row.id for row in keyword_rows}
    fused = reciprocal_rank_fusion(
        [[r.id for r in vector_rows], [r.id for r in keyword_rows], [r.id for r in aligned_rows]]
    )
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


_TABLE_RULE = "%| :%"  # the separator row of a Markdown table, as the OCR writes one ("| :--- | :--- |")


@dataclass(frozen=True)
class TopicMatch:
    objective_id: UUID
    subject_id: UUID
    similarity: float


@dataclass(frozen=True)
class TopicMatchResult:
    """Which topics a piece of text looks like, and how much the corpus actually supports saying so."""

    state: str  # HIGH | MEDIUM | LOW, by the subject's own retrieval thresholds
    matches: list[TopicMatch]


def topics_for_text(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    text: str,
    subject_ids: Sequence[UUID],
    limit: int = 3,
) -> TopicMatchResult:
    """The topics whose own pages are nearest to a piece of text — her homework photo, read out (F3).

    One embedding of the text is compared with the chunks of the given subjects, and each chunk votes for the
    objectives it is tagged to; a topic scores its nearest chunk, so a long chapter does not out-vote a short
    section. The state is computed with the same thresholds and the same rule the Tutor and lessons use, so a
    thin match says LOW here exactly as it would there — and the caller shows her nothing rather than guessing.

    Nothing is written: no retrieval log, because the text is her own worksheet and Scholr keeps none of it.
    """
    if not text.strip() or not subject_ids:
        return TopicMatchResult(state="LOW", matches=[])
    tiers: set[str] = set()
    thresholds: StateThresholds | None = None
    for subject in curriculum.subject_summaries(s, list(subject_ids)).values():
        try:
            config = subjects.explained_config_for(subject.code).retrieval
        except subjects.SubjectConfigError:
            continue
        tiers.update(config.allowed_authority_tiers)
        if thresholds is None:  # the first explained subject's thresholds; they are the same across subjects today
            thresholds = StateThresholds(
                high=config.state_thresholds.high,
                medium=config.state_thresholds.medium,
                low=config.state_thresholds.low,
            )
    if thresholds is None:
        return TopicMatchResult(state="LOW", matches=[])

    vector = gateway.embed([text], ctx)[0]
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    rows = s.execute(
        select(
            KnowledgeChunk.subject_id,
            KnowledgeChunk.objective_ids,
            KnowledgeChunk.authority_tier,
            distance.label("distance"),
        )
        .where(
            KnowledgeChunk.subject_id.in_(list(subject_ids)),
            KnowledgeChunk.authority_tier.in_(tiers),
            KnowledgeChunk.content_kind.not_in(NOT_RETRIEVABLE_KINDS),
            KnowledgeChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(CANDIDATES_PER_RANKING)
    ).all()

    best: dict[UUID, TopicMatch] = {}
    tier_of: dict[UUID, str] = {}
    for row in rows:
        similarity = 1.0 - float(row.distance)
        for objective_id in row.objective_ids or []:
            held = best.get(objective_id)
            if held is None or similarity > held.similarity:
                best[objective_id] = TopicMatch(objective_id, row.subject_id, round(similarity, 4))
                tier_of[objective_id] = row.authority_tier
    matches = sorted(best.values(), key=lambda m: m.similarity, reverse=True)[:limit]
    state = retrieval_state(
        [Candidate(m.similarity, False, True, tier_of[m.objective_id]) for m in matches],
        objective_scoped=False,
        thresholds=thresholds,
    )
    # The bar lessons already use: HIGH or MEDIUM, or her books do not support naming a topic at all.
    return TopicMatchResult(state=state, matches=matches if state in ("HIGH", "MEDIUM") else [])


def objective_tables(s: Session, *, subject_id: UUID, objective_id: UUID, limit: int = 4) -> list[RetrievedChunk]:
    """The book's own tables on one objective, in page order. Similarity ranking can leave a table out of the top
    passages (Chemistry 2.2's particle table, 22 Sep 2026), and a lesson's tables must be built from the book's."""
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        raise ValueError("unknown subject")
    config = subjects.explained_config_for(subject.code).retrieval
    rows = s.execute(
        select(KnowledgeChunk, Source.title)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .join(Source, Source.id == KnowledgeDocument.source_id)
        .where(
            KnowledgeChunk.subject_id == subject_id,
            KnowledgeChunk.authority_tier.in_(config.allowed_authority_tiers),
            KnowledgeChunk.content_kind.not_in(NOT_RETRIEVABLE_KINDS),
            KnowledgeChunk.objective_ids.any(objective_id),
            KnowledgeChunk.content.like(_TABLE_RULE),
        )
        .order_by(KnowledgeChunk.page_start)
        .limit(limit)
    ).all()
    return [
        RetrievedChunk(
            id=row.KnowledgeChunk.id,
            source_title=row.title,
            printed_page=(row.KnowledgeChunk.meta or {}).get("printed_page_start"),
            heading_path=row.KnowledgeChunk.heading_path,
            content_kind=row.KnowledgeChunk.content_kind,
            authority_tier=row.KnowledgeChunk.authority_tier,
            content=row.KnowledgeChunk.content,
            similarity=None,
            aligned=True,
            score=0.0,
        )
        for row in rows
    ]


def chunk_texts(s: Session, chunk_ids: Sequence[UUID]) -> dict[UUID, str]:
    """chunk_id -> content, for re-checking something written from those chunks (lessons, AC-U4)."""
    if not chunk_ids:
        return {}
    return dict(
        s.execute(select(KnowledgeChunk.id, KnowledgeChunk.content).where(KnowledgeChunk.id.in_(chunk_ids))).all()
    )  # type: ignore[arg-type]
