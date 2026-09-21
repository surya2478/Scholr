from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request

from app.core.deps import DbDep, PrincipalDep, SessionsDep, llm_gateway
from app.core.errors import ApiError
from app.core.rbac import Principal
from app.core.telemetry import request_id_of
from app.llm.gateway import CallContext
from app.modules.assessment import service as assessment
from app.modules.tutoring import service
from app.modules.tutoring.schemas import (
    EssayPlanIn,
    EssayPlanOut,
    HelpIn,
    MessageIn,
    MessageOut,
    NextItemOut,
    SessionCreate,
    SessionOut,
    SpeechIn,
    SpeechOut,
    TurnOut,
)

router = APIRouter(tags=["tutoring"])


def _ctx(request: Request, principal: Principal) -> CallContext:
    return CallContext(
        request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=principal.student_id
    )


@router.post("/tutor/sessions", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, principal: PrincipalDep, s: DbDep) -> SessionOut:
    return service.start_session(s, principal, body, now=datetime.now(UTC))


@router.get("/tutor/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: UUID, principal: PrincipalDep, s: DbDep) -> SessionOut:
    return service.get_session(s, principal, session_id)


@router.post("/tutor/sessions/{session_id}/next", response_model=NextItemOut)
def next_question(session_id: UUID, principal: PrincipalDep, s: DbDep) -> NextItemOut:
    return service.next_item(s, principal, session_id, now=datetime.now(UTC))


@router.post("/tutor/sessions/{session_id}/turns", response_model=TurnOut)
def send_turn(
    session_id: UUID, body: MessageIn, request: Request, principal: PrincipalDep, sessions: SessionsDep
) -> TurnOut:
    return service.send_message(
        sessions, llm_gateway(request), _ctx(request, principal), principal, session_id, body, now=datetime.now(UTC)
    )


@router.post("/tutor/sessions/{session_id}/turns/stream")
def stream_turn(session_id: UUID, body: MessageIn, request: Request, principal: PrincipalDep, sessions: SessionsDep):
    import json

    from fastapi.responses import StreamingResponse

    turn = service.send_message(
        sessions, llm_gateway(request), _ctx(request, principal), principal, session_id, body, now=datetime.now(UTC)
    )

    def event_generator():
        content = turn.reply.content
        chunk_size = 20
        for i in range(0, len(content), chunk_size):
            token = content[i : i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'turn': turn.model_dump(mode='json')})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/tutor/sessions/{session_id}/help", response_model=TurnOut)
def ask_for_help(
    session_id: UUID, body: HelpIn, request: Request, principal: PrincipalDep, sessions: SessionsDep
) -> TurnOut:
    return service.request_help(
        sessions, llm_gateway(request), _ctx(request, principal), principal, session_id, body, now=datetime.now(UTC)
    )


@router.post("/tutor/sessions/{session_id}/end", response_model=SessionOut)
def end_session(session_id: UUID, principal: PrincipalDep, s: DbDep) -> SessionOut:
    return service.end_session(s, principal, session_id, now=datetime.now(UTC))


@router.get("/tutor/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_messages(session_id: UUID, principal: PrincipalDep, s: DbDep) -> list[MessageOut]:
    return service.list_messages(s, principal, session_id)


@router.post("/tutor/speech", response_model=SpeechOut)
def post_speech(body: SpeechIn, request: Request, principal: PrincipalDep) -> SpeechOut:
    """Turn a spoken question into text for her message box. The recording is decoded, checked, passed to the
    gateway and dropped: it is not stored or logged (docs/STUDENT-APP.md §16)."""
    try:
        audio = base64.b64decode(body.audio, validate=True)
    except binascii.Error:
        raise ApiError(400, "bad_recording", "That recording could not be read. Try again, or type it.") from None
    heard = service.transcribe_speech(llm_gateway(request), _ctx(request, principal), audio)
    return SpeechOut(text=heard.text, unclear=heard.unclear)


@router.post("/tutor/essay-plan", response_model=EssayPlanOut)
def post_essay_plan(body: EssayPlanIn, request: Request, principal: PrincipalDep, s: DbDep) -> EssayPlanOut:
    """Plan an extended answer. Returns notes to write from — never the answer (AC-R5)."""
    plan, chunks = service.plan_essay(
        s,
        llm_gateway(request),
        _ctx(request, principal),
        subject_id=body.subject_id,
        item_id=body.question_item_id,
        message=body.message,
        student_id=principal.student_id,
    )
    item = assessment.servable_item(s, body.question_item_id)
    return EssayPlanOut(
        question_item_id=item.id,
        command_word=item.command_word,
        marks=item.marks,
        for_points=list(plan.for_points),
        against_points=list(plan.against_points),
        evidence=list(plan.evidence),
        conclusion_direction=plan.conclusion_direction,
        watch_out=list(plan.watch_out),
        refusal=plan.refusal,
        removed_as_prose=plan.dropped,
        citations=service.citations_out(chunks),
        rule_version=plan.rule_version,
    )
