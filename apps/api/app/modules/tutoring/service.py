"""Tutoring service: learning sessions, practice selection, help on a question and grounded explanations.

Turn shape (ARCHITECTURE §6): safety check -> policy decides (template, no LLM) or retrieval + tutor LLM -> guards
(answer leak, output safety, grounding labels) -> message + events. No transaction is held during the tutor call.
Inside a session the subject is known, so turns never call a router LLM (AC-A1).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_role, require_student_access
from app.llm.gateway import CallContext, LLMError, LLMGateway
from app.llm.text_repair import repair_json_escapes
from app.modules.assessment import service as assessment
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.evaluation import service as evaluation
from app.modules.events import service as events
from app.modules.knowledge import service as knowledge
from app.modules.mastery import service as mastery
from app.modules.memory import service as memory
from app.modules.mistakes import service as mistakes
from app.modules.safety import service as safety
from app.modules.subjects import service as subjects
from app.modules.tutoring import engine, planning, speech
from app.modules.tutoring.models import Conversation, LearningSession, Message
from app.modules.tutoring.policy import HelpDecision
from app.modules.tutoring.schemas import (
    CitationOut,
    HelpIn,
    MessageIn,
    MessageOut,
    NextItemOut,
    SessionCreate,
    SessionOut,
    SessionStateOut,
    TurnOut,
    TutorReply,
)

SessionOpener = Callable[[], AbstractContextManager[Session]]

TEMPLATES_FILE = Path(__file__).with_name("templates.yaml")
TUTOR_ROLE = "tutor"
HELP_PROMPT = "tutor_help"
EXPLAIN_PROMPT = "tutor_explain"
RECENT_ITEM_DAYS = 14
MAX_EXCERPTS = 3
EXCERPT_CHARS = 900
CONVERSATION_MESSAGES = 6
CONVERSATION_CHARS = 600
MAX_ACTIVE_MINUTES = 240
GENERAL_KNOWLEDGE_NOTE = "Part of this is general knowledge, not from your course materials."
NO_NOTES = "(none yet)"


@lru_cache
def templates() -> dict[str, str]:
    return yaml.safe_load(TEMPLATES_FILE.read_text(encoding="utf-8"))["replies"]


# ---------------------------------------------------------------------------
# Rows and views
# ---------------------------------------------------------------------------


def session_exists(s: Session, session_id: UUID) -> bool:
    """True if the session exists and is visible to the caller (row-level security)."""
    return s.scalar(select(LearningSession.id).where(LearningSession.id == session_id)) is not None


def _session_row(s: Session, principal: Principal, session_id: UUID, *, write: bool) -> LearningSession:
    row = s.get(LearningSession, session_id)
    if row is None:
        raise not_found("session")
    if write:
        if principal.role != "student" or principal.student_id != row.student_id:
            raise ApiError(403, "forbidden", "only the student can use this session")
    else:
        require_student_access(principal, row.student_id, "conversations")
    return row


def _require_open(row: LearningSession) -> None:
    if row.ended_at is not None:
        raise ApiError(409, "session_ended", "this session has ended")


def _session_out(row: LearningSession) -> SessionOut:
    state = engine.SessionState.load(row.state)
    return SessionOut(
        id=row.id,
        subject_id=row.subject_id,
        objective_id=row.objective_id,
        mode=row.mode,
        command_word=row.command_word,
        started_at=row.started_at,
        ended_at=row.ended_at,
        active_minutes=row.active_minutes,
        state=SessionStateOut(
            phase=state.phase,
            item_id=UUID(state.item_id) if state.item_id else None,
            help_level=state.help_level,
            needs_similar_question=state.needs_isomorphic,
        ),
    )


def _message_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role,
        content=m.content,
        assistance_level=m.assistance_level,
        retrieval_state=m.retrieval_state,
        citations=[CitationOut(**c) for c in m.citations or []],
        safety_status=m.safety_status,
        created_at=m.created_at,
    )


def _add_message(
    s: Session,
    row: LearningSession,
    *,
    role: str,
    content: str,
    assistance_level: int = 0,
    retrieval_state: str | None = None,
    citations: Sequence[dict[str, Any]] = (),
    safety_status: str = "allow",
) -> Message:
    conversation_id = s.scalar(select(Conversation.id).where(Conversation.session_id == row.id))
    message = Message(
        tenant_id=row.tenant_id,
        student_id=row.student_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        assistance_level=assistance_level,
        retrieval_state=retrieval_state,
        citations=list(citations),
        safety_status=safety_status,
        created_at=datetime.now(UTC),
    )
    s.add(message)
    s.flush()
    return message


def _recent_conversation(s: Session, row: LearningSession, *, exclude: UUID | None = None) -> str:
    conversation_id = s.scalar(select(Conversation.id).where(Conversation.session_id == row.id))
    rows = s.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.id != exclude if exclude else True)
        .order_by(Message.created_at.desc())
        .limit(CONVERSATION_MESSAGES)
    ).all()
    return "\n".join(f"{m.role}: {m.content[:CONVERSATION_CHARS]}" for m in reversed(rows)) or "(none)"


def _citation(chunk: knowledge.RetrievedChunk) -> dict[str, Any]:
    return {"source_title": chunk.source_title, "printed_page": chunk.printed_page, "heading_path": chunk.heading_path}


def citations_out(chunks: Sequence[knowledge.RetrievedChunk]) -> list[CitationOut]:
    """Where a plan's material came from — her own course book, named and paged."""
    return [CitationOut(**_citation(c)) for c in chunks]


def _excerpts(chunks: Sequence[knowledge.RetrievedChunk]) -> str:
    if not chunks:
        return "(no course material found)"
    return "\n\n".join(
        f"[{i}] {c.source_title}, p.{c.printed_page} — {c.heading_path or ''}\n{c.content[:EXCERPT_CHARS]}"
        for i, c in enumerate(chunks, start=1)
    )


def _learning_notes(s: Session, *, student_id: UUID | None, subject_id: UUID) -> str:
    """Active learning memory for the prompt (AC-M3 statements, each backed by events)."""
    if student_id is None:
        return NO_NOTES
    notes = memory.memory_for_prompt(s, student_id=student_id, subject_id=subject_id)
    return "\n".join(f"- {n}" for n in notes) or NO_NOTES


def _mastery_levels(s: Session, row: LearningSession) -> dict[UUID, int]:
    return {
        m.objective_id: m.level for m in mastery.list_mastery(s, student_id=row.student_id, subject_id=row.subject_id)
    }


def _event_common(row: LearningSession, now: datetime, objective_ids: Sequence[UUID]) -> dict[str, Any]:
    return {
        "tenant_id": row.tenant_id,
        "student_id": row.student_id,
        "occurred_at": now,
        "subject_id": row.subject_id,
        "objective_ids": list(objective_ids),
        "ref_type": "session",
        "ref_id": row.id,
    }


def _safety_turn(
    s: Session, gateway: LLMGateway, ctx: CallContext, row: LearningSession, text: str, now: datetime
) -> tuple[Message, TurnOut | None]:
    """Store the student's message and run the safety pipeline. Returns a finished turn when safety blocks."""
    student_message = _add_message(s, row, role="student", content=text)
    outcome = safety.check_input(
        s,
        gateway,
        ctx,
        tenant_id=row.tenant_id,
        student_id=row.student_id,
        text=text,
        context=_recent_conversation(s, row, exclude=student_message.id),
        message_id=student_message.id,
        now=now,
    )
    if not outcome.blocks_tutoring:
        return student_message, None
    student_message.safety_status = outcome.decision.action
    reply = _add_message(s, row, role="tutor", content=outcome.response or "", safety_status=outcome.decision.action)
    return student_message, TurnOut(session=_session_out(row), kind="safety", reply=_message_out(reply))


def _notice(s: Session, row: LearningSession, key: str, retrieval_state: str | None = None) -> TurnOut:
    reply = _add_message(s, row, role="tutor", content=templates()[key], retrieval_state=retrieval_state)
    return TurnOut(session=_session_out(row), kind="notice", reply=_message_out(reply))


# ---------------------------------------------------------------------------
# Sessions and practice selection
# ---------------------------------------------------------------------------


def start_session(s: Session, principal: Principal, body: SessionCreate, *, now: datetime) -> SessionOut:
    require_role(principal, "student")
    assert principal.student_id is not None
    summary_of = curriculum.subject_summaries(s, [body.subject_id])
    if body.subject_id not in summary_of:
        raise not_found("subject")
    # Clearing a doubt works wherever Scholr explains a subject from her own books, which from 20 Sep 2026
    # includes a lessons-only subject like Physics (docs/STUDENT-APP.md D4, amended). Practice and tests still
    # need a taught subject: they set and mark questions, which a lessons-only subject has none of.
    config = subjects.config_for(summary_of[body.subject_id].code)
    if not (config.explains if body.mode == "learn" else config.taught_here):
        raise ApiError(409, "subject_not_taught", "The Tutor can't help with this subject yet.")
    if body.objective_id is not None:
        summary = curriculum.objective_summaries(s, [body.objective_id]).get(body.objective_id)
        if summary is None or summary.subject_id != body.subject_id:
            raise ApiError(422, "objective_not_in_subject", "the objective does not belong to this subject")
    command_word = (body.command_word or "").strip().lower() or None
    if command_word and not assessment.candidate_items(s, subject_id=body.subject_id, command_word=command_word):
        # Better to refuse than to open a drill that will say "no questions" on its first turn.
        raise ApiError(422, "no_items_for_command_word", "there are no questions asking for that yet")
    row = LearningSession(
        tenant_id=principal.tenant_id,
        student_id=principal.student_id,
        subject_id=body.subject_id,
        objective_id=body.objective_id,
        mode=body.mode,
        command_word=command_word,
        state=engine.SessionState().dump(),
        started_at=now,
    )
    s.add(row)
    s.flush()
    s.add(Conversation(tenant_id=principal.tenant_id, student_id=principal.student_id, session_id=row.id))
    events.append(
        s,
        event_type="session_started",
        payload={"session_id": row.id, "mode": body.mode},
        **_event_common(row, now, [body.objective_id] if body.objective_id else []),
    )
    return _session_out(row)


def get_session(s: Session, principal: Principal, session_id: UUID) -> SessionOut:
    return _session_out(_session_row(s, principal, session_id, write=False))


def next_item(s: Session, principal: Principal, session_id: UUID, *, now: datetime) -> NextItemOut:
    row = _session_row(s, principal, session_id, write=True)
    _require_open(row)
    state = engine.SessionState.load(row.state)
    items = {
        item.id: item
        for item in assessment.candidate_items(s, subject_id=row.subject_id, command_word=row.command_word)
    }
    candidates = [engine.ItemCandidate(i.id, i.objective_ids, i.marks, i.source_ref) for i in items.values()]
    selection = {
        "mastery_levels": _mastery_levels(s, row),
        "mistake_objectives": {
            m.objective_id
            for m in mistakes.list_mistakes(s, student_id=row.student_id, subject_id=row.subject_id, status="open")
            if m.objective_id
        },
        "recent_item_ids": assessment.recent_item_ids(
            s, student_id=row.student_id, since=now - timedelta(days=RECENT_ITEM_DAYS)
        )
        | {UUID(i) for i in state.served_item_ids},
        "preferred_objectives": {row.objective_id} if row.objective_id else set(),
    }
    required = {UUID(o) for o in state.isomorphic_objective_ids} if state.needs_isomorphic else set()
    chosen = engine.choose_item(candidates, required_objectives=required, **selection)
    if chosen is None and required:
        chosen = engine.choose_item(candidates, **selection)  # nothing similar available: continue, flag stays set
    if chosen is None:
        return NextItemOut(session=_session_out(row), question=None, notice=templates()["no_items"])
    row.state = engine.start_item(state, chosen.id, chosen.objective_ids).dump()
    s.flush()
    return NextItemOut(session=_session_out(row), question=assessment.question_out(items[chosen.id]))


def end_session(s: Session, principal: Principal, session_id: UUID, *, now: datetime) -> SessionOut:
    row = _session_row(s, principal, session_id, write=True)
    if row.ended_at is None:
        row.ended_at = now
        row.active_minutes = min(MAX_ACTIVE_MINUTES, int((now - row.started_at).total_seconds() // 60))
        state = engine.SessionState.load(row.state)
        row.state = engine.SessionState(**{**state.__dict__, "phase": "ended"}).dump()
        events.append(
            s,
            event_type="session_ended",
            payload={"session_id": row.id, "active_minutes": row.active_minutes},
            **_event_common(row, now, [row.objective_id] if row.objective_id else []),
        )
        s.flush()
    return _session_out(row)


@dataclass(frozen=True)
class SessionBrief:
    id: UUID
    tenant_id: UUID
    student_id: UUID
    subject_id: UUID
    started_at: datetime
    ended_at: datetime


def sessions_to_summarize(s: Session, *, limit: int = 50) -> list[UUID]:
    """Ended sessions not yet processed by the learning memory job, oldest first."""
    return list(
        s.scalars(
            select(LearningSession.id)
            .where(LearningSession.ended_at.is_not(None), LearningSession.memory_summarized_at.is_(None))
            .order_by(LearningSession.ended_at)
            .limit(limit)
        )
    )


def session_brief(s: Session, session_id: UUID) -> SessionBrief | None:
    row = s.get(LearningSession, session_id)
    if row is None or row.ended_at is None:
        return None
    return SessionBrief(row.id, row.tenant_id, row.student_id, row.subject_id, row.started_at, row.ended_at)


def mark_summarized(s: Session, session_id: UUID, *, now: datetime) -> None:
    row = s.get(LearningSession, session_id)
    if row is not None:
        row.memory_summarized_at = now
        s.flush()


def list_messages(s: Session, principal: Principal, session_id: UUID) -> list[MessageOut]:
    row = _session_row(s, principal, session_id, write=False)
    if principal.role != "student":  # AC-S2: guardian/admin reads of conversations are audited
        audit.record(
            s,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            action="tutoring.conversation_read",
            entity_type="learning_session",
            entity_id=row.id,
            student_id=row.student_id,
        )
    conversation_id = s.scalar(select(Conversation.id).where(Conversation.session_id == row.id))
    return [
        _message_out(m)
        for m in s.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
        )
    ]


# ---------------------------------------------------------------------------
# Help on the current question (help ladder)
# ---------------------------------------------------------------------------


def _item_progress(s: Session, row: LearningSession, item_id: UUID) -> tuple[engine.ItemProgress, UUID | None]:
    history = events.list_events(s, student_id=row.student_id, types=("attempt_submitted", "attempt_evaluated"))
    attempt_ids = [
        ev.payload["attempt_id"]
        for ev in history
        if ev.type == "attempt_submitted"
        and ev.payload.get("session_id") == str(row.id)
        and ev.payload.get("question_item_id") == str(item_id)
    ]
    wanted = set(attempt_ids)
    misses = sum(
        1
        for ev in history
        if ev.type == "attempt_evaluated"
        and ev.payload.get("attempt_id") in wanted
        and float(ev.payload["marks_awarded"]) < float(ev.payload["marks_available"])
    )
    return engine.ItemProgress(len(attempt_ids), misses), (UUID(attempt_ids[-1]) if attempt_ids else None)


@dataclass(frozen=True)
class _HelpContext:
    decision: HelpDecision
    item: assessment.ItemView
    attempt_id: UUID | None
    chunks: list[knowledge.RetrievedChunk]
    retrieval_state: str
    variables: dict[str, str]


def _help_locked(s: Session, row: LearningSession) -> bool:
    """No help in test-mode sessions, nor in any session while a study test or timed sitting is in progress
    (AC-L5, AC-R3)."""
    return (
        row.mode in engine.NO_HELP_MODES or assessment.active_exam_assessment(s, student_id=row.student_id) is not None
    )


def request_help(
    open_session: SessionOpener,
    gateway: LLMGateway,
    ctx: CallContext,
    principal: Principal,
    session_id: UUID,
    body: HelpIn,
    *,
    now: datetime,
) -> TurnOut:
    with open_session() as s:
        row = _session_row(s, principal, session_id, write=True)
        _require_open(row)
        if body.message:
            _, blocked = _safety_turn(s, gateway, ctx, row, body.message, now)
            if blocked:
                return blocked
        if _help_locked(s, row):  # AC-L5
            return _notice(s, row, "no_help_in_test")
        state = engine.SessionState.load(row.state)
        if not state.item_id:
            raise ApiError(409, "no_active_question", "ask for a question first")
        item = assessment.servable_item(s, UUID(state.item_id))
        progress, attempt_id = _item_progress(s, row, item.id)
        levels = _mastery_levels(s, row)
        mastery_level = min((levels.get(o, 0) for o in item.objective_ids), default=0)
        decision = engine.decide_help(state, progress=progress, mastery_level=mastery_level, now=now)
        events.append(
            s,
            event_type="help_requested",
            payload={"session_id": row.id, "attempt_id": attempt_id},
            **_event_common(row, now, item.objective_ids),
        )
        if decision.action == "ask_for_attempt":  # AC-L1: no LLM, nothing revealed
            row.state = engine.after_help(state, decision, now).dump()
            reply = _add_message(s, row, role="tutor", content=templates()["ask_for_attempt"])
            return TurnOut(session=_session_out(row), kind="ask_for_attempt", reply=_message_out(reply))

        working = feedback = "(none yet)"
        if attempt_id is not None:
            attempt = assessment.get_attempt(s, principal, attempt_id)
            parts = [
                attempt.working_for_marking,
                f"Final answer: {attempt.final_answer}" if attempt.final_answer else None,
            ]
            working = "\n".join(p for p in parts if p) or working
            evaluation_id = evaluation.latest_id_for_attempt(s, attempt_id)
            if evaluation_id is not None:
                marked = evaluation.get_evaluation(s, principal, evaluation_id)
                feedback = f"{marked.marks_awarded:g}/{marked.marks_available:g} marks. {marked.feedback.summary}"
        subject = curriculum.subject_summaries(s, [row.subject_id])[row.subject_id]
        objectives = curriculum.objective_summaries(s, list(item.objective_ids))
        objective_text = "; ".join(o.statement for o in objectives.values()) or "not set"
        retrieval = knowledge.search(
            s,
            gateway,
            ctx,
            query=f"{objective_text} {item.stem}"[:500],
            subject_id=row.subject_id,
            objective_ids=list(item.objective_ids),
            k=MAX_EXCERPTS,
        )
        help_ctx = _HelpContext(
            decision=decision,
            item=item,
            attempt_id=attempt_id,
            chunks=retrieval.chunks,
            retrieval_state=retrieval.state,
            variables={
                "subject": subject.name,
                "objective": objective_text,
                "level": str(int(decision.level)),
                "level_name": engine.HELP_LEVEL_NAMES[decision.level],
                "question": f"{item.context or ''}\n{item.stem}".strip(),
                "working": working,
                "feedback": feedback,
                "student_message": body.message or "(asked for help)",
                "excerpts": _excerpts(retrieval.chunks),
                "learning_notes": _learning_notes(s, student_id=row.student_id, subject_id=row.subject_id),
            },
        )

    try:
        result = gateway.structured(TUTOR_ROLE, HELP_PROMPT, help_ctx.variables, TutorReply, ctx)
    except LLMError:
        with open_session() as s:
            return _notice(s, _session_row(s, principal, session_id, write=True), "tutor_unavailable")

    reply = result.value
    with open_session() as s:
        row = _session_row(s, principal, session_id, write=True)
        text = repair_json_escapes(reply.message)
        question_text = f"{help_ctx.item.context or ''} {help_ctx.item.stem}"
        withheld = bool(safety.output_issues(text)) or engine.leaks_answer(
            text, help_ctx.item.answer_spec, help_level=int(help_ctx.decision.level), question_text=question_text
        )
        check_question = None if withheld else reply.check_question
        content = (
            templates()["reply_withheld"] if withheld else text + (f"\n\n{check_question}" if check_question else "")
        )
        shown = engine.usable_citations(reply.citations, state=help_ctx.retrieval_state, excerpts=len(help_ctx.chunks))
        citations = [] if withheld else [_citation(help_ctx.chunks[i - 1]) for i in shown]
        message = _add_message(
            s,
            row,
            role="tutor",
            content=content,
            assistance_level=int(help_ctx.decision.level),
            retrieval_state=help_ctx.retrieval_state,
            citations=citations,
            safety_status="withheld" if withheld else "allow",
        )
        state = engine.SessionState.load(row.state)
        row.state = engine.after_help(state, help_ctx.decision, now, help_ctx.item.objective_ids).dump()
        events.append(
            s,
            event_type="help_given",
            payload={"level": int(help_ctx.decision.level), "session_id": row.id, "attempt_id": help_ctx.attempt_id},
            **_event_common(row, now, help_ctx.item.objective_ids),
        )
        return TurnOut(
            session=_session_out(row), kind="help", reply=_message_out(message), check_question=check_question
        )


# ---------------------------------------------------------------------------
# Grounded explanation (free-text message)
# ---------------------------------------------------------------------------


def _citation_rule(required: Sequence[str]) -> str:
    if required:
        kinds = ", ".join(r.replace("_", " ") for r in required)
        return f"Every {kinds} you mention must come from a cited excerpt; otherwise leave it out."
    return "Cite excerpts for syllabus scope, notation, method conventions and exam technique."


@dataclass(frozen=True)
class PreparedExplanation:
    variables: dict[str, str]
    plan: engine.GroundingPlan
    chunks: list[knowledge.RetrievedChunk]
    retrieval_state: str


def prepare_explanation(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    subject_id: UUID,
    objective_id: UUID | None,
    message: str,
    conversation: str = "",
    student_id: UUID | None = None,
) -> PreparedExplanation:
    """Retrieval, grounding plan and prompt variables for one explanation turn (shared with the tutor eval)."""
    subject = curriculum.subject_summaries(s, [subject_id])[subject_id]
    config = subjects.explained_config_for(subject.code)
    objective_ids = [objective_id] if objective_id else []
    retrieval = knowledge.search(
        s, gateway, ctx, query=message, subject_id=subject_id, objective_ids=objective_ids, k=MAX_EXCERPTS
    )
    plan = engine.grounding_plan(retrieval.state, citation_critical=bool(config.retrieval.citation_required_for))
    objectives = curriculum.objective_summaries(s, objective_ids)
    variables = {
        "subject": subject.name,
        "objective": "; ".join(o.statement for o in objectives.values()) or "not set",
        "conversation": conversation,
        "student_message": message,
        "excerpts": _excerpts(retrieval.chunks),
        "citation_rule": _citation_rule(config.retrieval.citation_required_for),
        "learning_notes": _learning_notes(s, student_id=student_id, subject_id=subject_id),
    }
    return PreparedExplanation(variables, plan, list(retrieval.chunks), retrieval.state)


def send_message(
    open_session: SessionOpener,
    gateway: LLMGateway,
    ctx: CallContext,
    principal: Principal,
    session_id: UUID,
    body: MessageIn,
    *,
    now: datetime,
) -> TurnOut:
    with open_session() as s:
        row = _session_row(s, principal, session_id, write=True)
        _require_open(row)
        student_message, blocked = _safety_turn(s, gateway, ctx, row, body.message, now)
        if blocked:
            return blocked
        if _help_locked(s, row):
            return _notice(s, row, "no_help_in_test")
        prepared = prepare_explanation(
            s,
            gateway,
            ctx,
            subject_id=row.subject_id,
            objective_id=row.objective_id,
            message=body.message,
            conversation=_recent_conversation(s, row, exclude=student_message.id),
            student_id=row.student_id,
        )
        if not prepared.plan.answer_allowed:
            return _notice(s, row, "not_enough_material", prepared.retrieval_state)
        variables, plan = prepared.variables, prepared.plan
        chunks, retrieval_state = prepared.chunks, prepared.retrieval_state

    try:
        result = gateway.structured(TUTOR_ROLE, EXPLAIN_PROMPT, variables, TutorReply, ctx)
    except LLMError:
        with open_session() as s:
            return _notice(s, _session_row(s, principal, session_id, write=True), "tutor_unavailable", retrieval_state)

    reply = result.value
    with open_session() as s:
        row = _session_row(s, principal, session_id, write=True)
        text = repair_json_escapes(reply.message)
        withheld = bool(safety.output_issues(text))
        if withheld:
            content, check_question, citations = templates()["reply_withheld"], None, []
        else:
            suffixes = [plan.suffix] if plan.suffix else []
            if reply.uses_general_knowledge and plan.prefix is None:
                suffixes.append(GENERAL_KNOWLEDGE_NOTE)
            check_question = reply.check_question
            content = (plan.prefix or "") + text + "".join(f"\n\n{x}" for x in [*suffixes, check_question] if x)
            shown = engine.usable_citations(reply.citations, state=retrieval_state, excerpts=len(chunks))
            citations = [_citation(chunks[i - 1]) for i in shown]
        message = _add_message(
            s,
            row,
            role="tutor",
            content=content,
            retrieval_state=retrieval_state,
            citations=citations,
            safety_status="withheld" if withheld else "allow",
        )
        if row.objective_id is not None:
            events.append(
                s,
                event_type="explanation_viewed",
                payload={"session_id": row.id},
                **_event_common(row, now, [row.objective_id]),
            )
        return TurnOut(
            session=_session_out(row), kind="explanation", reply=_message_out(message), check_question=check_question
        )


# --- essay planning (Phase 2, AC-R5) --------------------------------------------------------------------

PLAN_ROLE = "essay_planner"
PLAN_PROMPT = "essay_plan"
# Wording that means "write it for me". Checked before the call: a request to draft is answered by Scholr,
# not sent to a model and hoped about.
_DRAFT_REQUEST = re.compile(
    r"\b(write|draft|compose)\s+(it|this|the|my|an?)\s*(answer|essay|response|paragraph)?|"
    r"\bwrite\s+(?:it|this|my|the)\b|\bdo\s+it\s+for\s+me\b|\bstart\s+(?:it|me)\s+off\b|"
    r"\bgive\s+me\s+(?:the|a|an)\s+(answer|essay|model answer|example paragraph)\b",
    re.I,
)


class EssayPlanOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    for_points: list[str] = Field(default_factory=list)
    against_points: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    conclusion_direction: str = ""
    watch_out: list[str] = Field(default_factory=list)
    refusal: str = ""


def asked_for_a_draft(message: str) -> bool:
    return bool(_DRAFT_REQUEST.search(message or ""))


def plan_essay(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    subject_id: UUID,
    item_id: UUID,
    message: str = "",
    student_id: UUID | None = None,
) -> tuple[planning.GuardedPlan, list[knowledge.RetrievedChunk]]:
    """Plan an extended answer. Returns the guarded plan — never prose (AC-R5)."""
    item = assessment.servable_item(s, item_id)
    subject = curriculum.subject_summaries(s, [subject_id])[subject_id]
    retrieval = knowledge.search(
        s,
        gateway,
        ctx,
        query=item.stem,
        subject_id=subject_id,
        objective_ids=list(item.objective_ids),
        k=MAX_EXCERPTS,
    )
    result = gateway.structured(
        PLAN_ROLE,
        PLAN_PROMPT,
        {
            "subject": subject.name,
            "marks": str(item.marks),
            "command_word": item.command_word or "not given",
            "stem": item.stem,
            "message": message,
            "excerpts": _excerpts(retrieval.chunks),
        },
        EssayPlanOutput,
        ctx,
    )
    value = result.value
    guarded = planning.guard(
        planning.PlanDraft(
            for_points=value.for_points,
            against_points=value.against_points,
            evidence=value.evidence,
            conclusion_direction=value.conclusion_direction,
            watch_out=value.watch_out,
            # Our sentence, not the model's, whenever she asked for the answer itself.
            refusal=planning.REFUSAL if asked_for_a_draft(message) or value.refusal else "",
        )
    )
    return guarded, retrieval.chunks


def transcribe_speech(gateway: LLMGateway, ctx: CallContext, audio: bytes) -> speech.Transcript:
    """Her spoken question as text for her to check (docs/STUDENT-APP.md §16). The recording is not stored."""
    return speech.transcribe(gateway, ctx, audio)
