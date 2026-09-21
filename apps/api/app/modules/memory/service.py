"""Learning memory (ARCHITECTURE §15): short, evidence-linked statements about how the student learns.

Summarizing runs in three steps so no transaction is held during the LLM call:
load the ended session's events as an id-only digest (no conversation text, no answers) → `summarizer` proposes
statements → `memory.rules` validates, merges and supersedes, then the rows are written.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import uuid7
from app.core.rbac import Principal, require_student_access
from app.llm.gateway import CallContext, LLMError, LLMGateway
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.events import service as events
from app.modules.memory import rules
from app.modules.memory.models import LearningMemory
from app.modules.memory.schemas import MemoryOut, SummaryOutput
from app.modules.tutoring import service as tutoring

SessionOpener = Callable[[], AbstractContextManager[Session]]
ROLE = "summarizer"
PROMPT = "memory_summarize"
DIGEST_TYPES = (
    "attempt_evaluated",
    "evaluation_overridden",
    "help_requested",
    "help_given",
    "mistake_diagnosed",
    "confidence_reported",
    "explanation_viewed",
    "self_explanation_given",
)
MIN_DIGEST_EVENTS = 2  # below this there is nothing to learn from, so no LLM call is made
PROMPT_MEMORY_LIMIT = 5


@dataclass(frozen=True)
class SummaryReport:
    session_id: UUID
    status: str  # summarized | little_activity | llm_failed | not_found
    created: int = 0
    merged: int = 0
    superseded: int = 0
    rejected: tuple[str, ...] = ()
    cost_usd: float = 0.0


def _describe(ev: events.EventView, codes: dict[UUID, str]) -> str:
    p = ev.payload
    objectives = ",".join(sorted(codes.get(o, "?") for o in ev.objective_ids)) or "-"
    detail = {
        "attempt_evaluated": lambda: (
            f"marks={p.get('marks_awarded'):g}/{p.get('marks_available'):g} "
            f"help_level={p.get('help_level')} status={p.get('status')}"
        ),
        "evaluation_overridden": lambda: f"reviewed_marks={p.get('marks_awarded'):g}/{p.get('marks_available'):g}",
        "help_given": lambda: f"level={p.get('level')}",
        "mistake_diagnosed": lambda: f"mistake={p.get('fingerprint')} severity={p.get('severity')}",
        "confidence_reported": lambda: f"confidence_before_answering={p.get('confidence')}/4",
    }.get(ev.type, lambda: "")()
    return f"{ev.type} objectives={objectives} {detail}".strip()


def build_digest(
    session_events: Sequence[events.EventView], codes: dict[UUID, str]
) -> tuple[dict[str, rules.DigestEvent], str]:
    digest: dict[str, rules.DigestEvent] = {}
    lines = []
    for n, ev in enumerate(session_events, start=1):
        ref = f"E{n}"
        digest[ref] = rules.DigestEvent(ref, ev.id, frozenset(ev.objective_ids))
        lines.append(f"{ref} {_describe(ev, codes)}")
    return digest, "\n".join(lines)


def _existing(s: Session, student_id: UUID, subject_id: UUID) -> list[rules.Existing]:
    rows = s.scalars(
        select(LearningMemory).where(
            LearningMemory.student_id == student_id,
            LearningMemory.subject_id == subject_id,
            LearningMemory.status == "active",
        )
    ).all()
    evidence = {ev.id: ev for ev in events.events_by_ids(s, [i for r in rows for i in r.evidence_event_ids])}
    return [
        rules.Existing(
            id=r.id,
            kind=r.kind,
            statement=r.statement,
            evidence=frozenset(r.evidence_event_ids),
            objective_ids=frozenset(
                o for i in r.evidence_event_ids if i in evidence for o in evidence[i].objective_ids
            ),
        )
        for r in rows
    ]


def summarize_session(
    open_session: SessionOpener, gateway: LLMGateway, session_id: UUID, *, request_id: str, now: datetime
) -> SummaryReport:
    with open_session() as s:
        brief = tutoring.session_brief(s, session_id)
        if brief is None:
            return SummaryReport(session_id, "not_found")
        session_events = [
            ev
            for ev in events.list_events(
                s, student_id=brief.student_id, types=DIGEST_TYPES, since=brief.started_at - timedelta(minutes=1)
            )
            if ev.subject_id == brief.subject_id and ev.occurred_at <= brief.ended_at + timedelta(minutes=1)
        ]
        if len(session_events) < MIN_DIGEST_EVENTS:
            tutoring.mark_summarized(s, session_id, now=now)
            return SummaryReport(session_id, "little_activity")
        codes = {
            oid: o.code
            for oid, o in curriculum.objective_summaries(
                s, [o for ev in session_events for o in ev.objective_ids]
            ).items()
        }
        digest, digest_text = build_digest(session_events, codes)
        existing = _existing(s, brief.student_id, brief.subject_id)
        subject = curriculum.subject_summaries(s, [brief.subject_id])[brief.subject_id]
    existing_text = "\n".join(f"- [{e.kind}] {e.statement}" for e in existing) or "(none)"

    ctx = CallContext(request_id=request_id, tenant_id=brief.tenant_id, student_id=brief.student_id)
    try:
        result = gateway.structured(
            ROLE,
            PROMPT,
            {"subject": subject.name, "digest": digest_text, "existing": existing_text},
            SummaryOutput,
            ctx,
        )
    except LLMError:
        return SummaryReport(session_id, "llm_failed")  # not marked: the next job run retries

    proposals = [rules.Proposal(p.kind, p.statement, tuple(p.evidence)) for p in result.value.statements]
    decision = rules.decide(proposals, digest, existing)
    superseded = 0
    with open_session() as s:
        for new in decision.new:
            memory_id = uuid7()
            s.add(
                LearningMemory(
                    id=memory_id,
                    tenant_id=brief.tenant_id,
                    student_id=brief.student_id,
                    subject_id=brief.subject_id,
                    kind=new.kind,
                    statement=new.statement,
                    evidence_event_ids=list(new.event_ids),
                    status="active",
                )
            )
            s.flush()
            for old_id in new.supersedes:
                old = s.get(LearningMemory, old_id)
                if old is not None and old.status == "active":
                    old.status = "superseded"
                    old.superseded_by = memory_id
                    superseded += 1
        for merge in decision.merges:
            row = s.get(LearningMemory, merge.existing_id)
            if row is not None:
                row.evidence_event_ids = [*row.evidence_event_ids, *merge.add_event_ids]
        tutoring.mark_summarized(s, session_id, now=now)
    return SummaryReport(
        session_id,
        "summarized",
        created=len(decision.new),
        merged=len(decision.merges),
        superseded=superseded,
        rejected=tuple(decision.rejected),
        cost_usd=result.cost_usd or 0.0,
    )


def memory_for_prompt(s: Session, *, student_id: UUID, subject_id: UUID, limit: int = PROMPT_MEMORY_LIMIT) -> list[str]:
    """Deterministic retrieval for prompts: most recent active statements for the subject."""
    rows = s.scalars(
        select(LearningMemory)
        .where(
            LearningMemory.student_id == student_id,
            LearningMemory.subject_id == subject_id,
            LearningMemory.status == "active",
        )
        .order_by(LearningMemory.updated_at.desc())
        .limit(limit)
    )
    return [f"[{r.kind}] {r.statement}" for r in rows]


def list_memory(
    s: Session,
    principal: Principal,
    *,
    student_id: UUID,
    subject_id: UUID | None = None,
    include_superseded: bool = False,
) -> list[MemoryOut]:
    require_student_access(principal, student_id, "memory")
    query = select(LearningMemory).where(LearningMemory.student_id == student_id)
    if subject_id is not None:
        query = query.where(LearningMemory.subject_id == subject_id)
    if not include_superseded:
        query = query.where(LearningMemory.status == "active")
    rows = s.scalars(query.order_by(LearningMemory.updated_at.desc())).all()
    if principal.role != "student":  # AC-S2: guardian/admin reads of memory are audited
        meta: dict[str, Any] = {"count": len(rows)}
        audit.record(
            s,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            action="memory.read",
            entity_type="student",
            entity_id=student_id,
            student_id=student_id,
            meta=meta,
        )
    return [
        MemoryOut(
            id=r.id,
            subject_id=r.subject_id,
            kind=r.kind,
            statement=r.statement,
            evidence_count=len(r.evidence_event_ids),
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
