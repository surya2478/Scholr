from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.deps import DbDep, PrincipalDep, RlsSessions, SessionsDep, SettingsDep, llm_gateway
from app.core.errors import ApiError
from app.core.ids import uuid7
from app.core.rbac import Principal, resolve_student_id
from app.core.telemetry import request_id_of
from app.llm.gateway import CallContext
from app.modules.assessment import service, storage
from app.modules.assessment.schemas import (
    AssessmentBriefOut,
    AssessmentCreate,
    AssessmentOut,
    AttemptCreate,
    AttemptMeta,
    AttemptOut,
    QuestionOut,
    TranscriptionConfirm,
)
from app.modules.evaluation import service as evaluation

router = APIRouter(tags=["assessment"])


def _assessment_out(s: Session, principal: Principal, assessment_id: UUID) -> AssessmentOut:
    attempts = service.assessment_attempts(s, principal, assessment_id)
    marks = evaluation.marks_for_attempts(s, list(attempts.values()))
    return service.assessment_detail(s, principal, assessment_id, marks)


@router.post("/assessments", response_model=AssessmentOut, status_code=201)
def post_assessment(
    body: AssessmentCreate, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> AssessmentOut:
    sid = resolve_student_id(principal, student_id, scope="assessments")
    assessment_id = service.create_assessment(s, principal, body, student_id=sid, now=datetime.now(UTC))
    return _assessment_out(s, principal, assessment_id)


@router.get("/assessments", response_model=list[AssessmentBriefOut])
def get_assessments(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[AssessmentBriefOut]:
    sid = resolve_student_id(principal, student_id, scope="assessments")
    return service.list_assessments(s, principal, student_id=sid)


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: UUID, principal: PrincipalDep, s: DbDep) -> AssessmentOut:
    return _assessment_out(s, principal, assessment_id)


@router.post("/assessments/{assessment_id}/start", response_model=AssessmentOut)
def start_assessment(assessment_id: UUID, principal: PrincipalDep, s: DbDep) -> AssessmentOut:
    service.start_assessment(s, principal, assessment_id, now=datetime.now(UTC))
    return _assessment_out(s, principal, assessment_id)


@router.post("/assessments/{assessment_id}/submit", response_model=AssessmentOut)
def submit_assessment(assessment_id: UUID, principal: PrincipalDep, s: DbDep) -> AssessmentOut:
    service.submit_assessment(s, principal, assessment_id, now=datetime.now(UTC))
    return _assessment_out(s, principal, assessment_id)


@router.get("/questions/{item_id}", response_model=QuestionOut)
def get_question(item_id: UUID, s: DbDep) -> QuestionOut:
    return service.question_out(service.servable_item(s, item_id))


@router.post("/attempts", response_model=AttemptOut, status_code=201)
def post_attempt(body: AttemptCreate, principal: PrincipalDep, s: DbDep, response: Response) -> AttemptOut:
    existing = service.existing_attempt(s, principal, body)
    if existing is not None:
        response.status_code = 200
        return service.attempt_out(existing, evaluation.latest_id_for_attempt(s, existing.id))
    view = service.create_attempt(
        s, principal, body, now=datetime.now(UTC), working=body.working, final_answer=body.final_answer
    )
    return service.attempt_out(view, None)


def _transcribe(request: Request, principal: Principal, sessions: RlsSessions, uploads, attempt_id: UUID) -> AttemptOut:  # noqa: ANN001
    with sessions() as s:
        view = service.get_attempt(s, principal, attempt_id)
        service.check_can_transcribe(
            principal, view, evaluated=evaluation.latest_id_for_attempt(s, attempt_id) is not None
        )
    try:
        photos = [storage.load_photo(uploads, uri) for uri in view.photo_uris]
    except storage.UploadError as exc:
        raise ApiError(409, exc.code, exc.message) from None
    ctx = CallContext(request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=principal.student_id)
    result = service.transcribe(llm_gateway(request), ctx, stem=view.item.stem, photos=photos)
    with sessions() as s:
        return service.attempt_out(service.save_transcription(s, principal, attempt_id, result), None)


@router.post("/attempts/photo", response_model=AttemptOut, status_code=201)
def post_photo_attempt(
    request: Request,
    response: Response,
    principal: PrincipalDep,
    sessions: SessionsDep,
    settings: SettingsDep,
    question_item_id: Annotated[UUID, Form()],
    idempotency_key: Annotated[str, Form()],
    photos: Annotated[list[UploadFile], File()],
    pre_confidence: Annotated[int | None, Form()] = None,
    assessment_id: Annotated[UUID | None, Form()] = None,
    session_id: Annotated[UUID | None, Form()] = None,
    time_spent_s: Annotated[int | None, Form()] = None,
) -> AttemptOut:
    try:
        meta = AttemptMeta(
            question_item_id=question_item_id,
            idempotency_key=idempotency_key,
            pre_confidence=pre_confidence,
            assessment_id=assessment_id,
            session_id=session_id,
            time_spent_s=time_spent_s,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None

    with sessions() as s:
        existing = service.existing_attempt(s, principal, meta)
        if existing is not None:
            response.status_code = 200
            return service.attempt_out(existing, evaluation.latest_id_for_attempt(s, existing.id))
    if not 1 <= len(photos) <= storage.MAX_PHOTOS:
        raise ApiError(422, "invalid_photos", f"attach between 1 and {storage.MAX_PHOTOS} photos")

    uploads = settings.resolve_path(settings.uploads_dir)
    attempt_id = uuid7()
    uris: list[str] = []
    try:
        assert principal.student_id is not None
        for index, upload in enumerate(photos):
            data = upload.file.read(storage.MAX_BYTES + 1)
            uris.append(storage.save_photo(uploads, principal.student_id, attempt_id, index, data))
        with sessions() as s:
            service.create_attempt(s, principal, meta, now=datetime.now(UTC), photo_uris=uris, attempt_id=attempt_id)
    except storage.UploadError as exc:
        storage.delete_photos(uploads, uris)
        raise ApiError(422, exc.code, exc.message) from None
    except Exception:
        storage.delete_photos(uploads, uris)
        raise
    # The attempt and photos are saved; if transcription fails the student can retry /transcribe.
    return _transcribe(request, principal, sessions, uploads, attempt_id)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: UUID, principal: PrincipalDep, s: DbDep) -> AttemptOut:
    view = service.get_attempt(s, principal, attempt_id)
    return service.attempt_out(view, evaluation.latest_id_for_attempt(s, attempt_id))


@router.post("/attempts/{attempt_id}/transcribe", response_model=AttemptOut)
def retry_transcription(
    attempt_id: UUID, request: Request, principal: PrincipalDep, sessions: SessionsDep, settings: SettingsDep
) -> AttemptOut:
    return _transcribe(request, principal, sessions, settings.resolve_path(settings.uploads_dir), attempt_id)


@router.put("/attempts/{attempt_id}/transcription", response_model=AttemptOut)
def confirm_transcription(
    attempt_id: UUID, body: TranscriptionConfirm, principal: PrincipalDep, s: DbDep
) -> AttemptOut:
    evaluated = evaluation.latest_id_for_attempt(s, attempt_id) is not None
    view = service.confirm_transcription(s, principal, attempt_id, body, now=datetime.now(UTC), evaluated=evaluated)
    return service.attempt_out(view, None)
