from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Request, Response, UploadFile

from app.core.deps import DbDep, PrincipalDep, SessionsDep, SettingsDep, llm_gateway
from app.core.errors import ApiError
from app.core.rbac import Principal, require_role, resolve_student_id
from app.core.telemetry import request_id_of
from app.llm.gateway import CallContext, LLMError
from app.modules.learn import audio, homework, service
from app.modules.learn.schemas import (
    HomeworkPhotoOut,
    LessonOut,
    PastPapersOut,
    StreamOut,
    SubjectLearnOut,
    TopicOut,
    VivaQuestionOut,
    VivaStepIn,
    VivaStepOut,
    VivaTopicOut,
)

router = APIRouter(tags=["learn"])


def _student(principal: Principal, student_id: UUID | None) -> UUID | None:
    """Whose mastery to show. A parent sees the linked student's; an admin with no student sees none."""
    if principal.role == "admin" and student_id is None:
        return None
    return resolve_student_id(principal, student_id, scope=service.SCOPE)


@router.get("/learn/streams", response_model=list[StreamOut])
def get_streams(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[StreamOut]:
    return service.streams(s, student_id=_student(principal, student_id))


@router.get("/learn/subjects/{subject_id}", response_model=SubjectLearnOut)
def get_subject(subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> SubjectLearnOut:
    return service.subject_view(s, subject_id, student_id=_student(principal, student_id), now=datetime.now(UTC))


@router.get("/learn/subjects/{subject_id}/past-papers", response_model=PastPapersOut)
def get_past_papers(
    subject_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> PastPapersOut:
    return service.past_papers(s, subject_id, student_id=_student(principal, student_id), now=datetime.now(UTC))


@router.get("/learn/objectives/{objective_id}", response_model=TopicOut)
def get_topic(objective_id: UUID, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> TopicOut:
    return service.topic_view(s, objective_id, student_id=_student(principal, student_id), now=datetime.now(UTC))


@router.post("/learn/objectives/{objective_id}/lesson", response_model=LessonOut)
def post_lesson(objective_id: UUID, request: Request, principal: PrincipalDep, sessions: SessionsDep) -> LessonOut:
    """Write the topic's lesson if it has none yet (first reader pays; later readers get the stored one)."""
    student_id = _student(principal, None) if principal.role != "admin" else None
    now = datetime.now(UTC)
    with sessions() as s:
        topic = service.topic_view(s, objective_id, student_id=student_id, now=now)
        if not topic.lesson_available:
            raise ApiError(409, "lesson_not_available", topic.notice or "No lesson for this topic.")
        ctx = CallContext(request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=student_id)
        gateway = llm_gateway(request)
        prepared = service.prepare_lesson(s, gateway, ctx, objective_id)
        if not isinstance(prepared, service.PreparedLesson):
            return service.lesson_out(prepared)
    try:
        written = service.write_lesson(gateway, ctx, prepared)
    except LLMError as exc:
        raise ApiError(503, "lesson_unavailable", "The lesson could not be written just now. Try again soon.") from exc
    with sessions() as s:
        return service.lesson_out(service.record_lesson(s, prepared, written, actor=principal, now=now))


@router.post("/learn/objectives/{objective_id}/read", status_code=204)
def post_read(objective_id: UUID, principal: PrincipalDep, s: DbDep) -> None:
    service.record_read(s, principal, objective_id, now=datetime.now(UTC))


@router.get("/learn/objectives/{objective_id}/audio")
@router.head("/learn/objectives/{objective_id}/audio")
def get_lesson_audio(
    objective_id: UUID,
    request: Request,
    principal: PrincipalDep,
    s: DbDep,
    settings: SettingsDep,
    part: Literal["summary", "section", "example", "all"] = "all",
    index: int = 0,
    voice: str = audio.DEFAULT_VOICE,
) -> Response:
    """Stream synthesized lesson speech using Kokoro 82M (cached on disk)."""
    now = datetime.now(UTC)
    topic = service.topic_view(s, objective_id, student_id=_student(principal, None), now=now)
    if not topic.lesson or topic.lesson.status != "ready":
        raise ApiError(404, "lesson_not_found", "No ready lesson found for this topic.")

    text = audio.extract_speech_text(topic.lesson, part=part, index=index)
    if not text.strip():
        raise ApiError(400, "empty_text", "No text found for requested lesson component.")

    ctx = CallContext(
        request_id=request_id_of(request),
        tenant_id=principal.tenant_id,
        student_id=principal.student_id,
    )
    try:
        audio_bytes = audio.get_or_synthesize_audio(llm_gateway(request), ctx, settings, text, voice=voice)
    except LLMError as exc:
        # The provider's own message stays in llm_call; the page gets a plain reason.
        raise ApiError(503, "audio_unavailable", "The voice isn't available right now. Try again later.") from exc

    if not audio_bytes or len(audio_bytes) < 100:
        raise ApiError(502, "audio_failed", "Failed to generate audio stream from voice provider.")

    headers = {
        "Cache-Control": "private, max-age=86400",
        "Content-Length": str(len(audio_bytes)),
        "Accept-Ranges": "bytes",
    }
    if request.method == "HEAD":
        return Response(content=b"", media_type="audio/mpeg", headers=headers)

    # Signed-in content: the browser may keep it, a shared cache may not.
    return Response(content=audio_bytes, media_type="audio/mpeg", headers=headers)


@router.get("/learn/objectives/{objective_id}/podcast")
@router.head("/learn/objectives/{objective_id}/podcast")
def get_topic_podcast(
    objective_id: UUID,
    request: Request,
    principal: PrincipalDep,
    s: DbDep,
    settings: SettingsDep,
) -> Response:
    """Stream NotebookLM or podcast audio file for this objective."""
    now = datetime.now(UTC)
    topic = service.topic_view(s, objective_id, student_id=_student(principal, None), now=now)
    podcasts_dir = settings.private_content_dir / "podcasts"
    file_path = None
    if (podcasts_dir / f"{objective_id}.mp3").exists():
        file_path = podcasts_dir / f"{objective_id}.mp3"
    elif topic and topic.objective and (podcasts_dir / f"{topic.objective.code}.mp3").exists():
        file_path = podcasts_dir / f"{topic.objective.code}.mp3"

    if file_path and file_path.stat().st_size > 0:
        audio_bytes = file_path.read_bytes()
        headers = {
            "Cache-Control": "private, max-age=86400",
            "Content-Length": str(len(audio_bytes)),
            "Accept-Ranges": "bytes",
        }
        if request.method == "HEAD":
            return Response(content=b"", media_type="audio/mpeg", headers=headers)
        return Response(content=audio_bytes, media_type="audio/mpeg", headers=headers)

    # Fallback to lesson audio if ready
    if topic.lesson and topic.lesson.status == "ready":
        text = ""
        if topic.lesson.podcast_script:
            text = " ".join(f"{turn.speaker}: {turn.text}" for turn in topic.lesson.podcast_script)
        else:
            text = audio.extract_speech_text(topic.lesson, part="all")
        if text.strip():
            ctx = CallContext(
                request_id=request_id_of(request),
                tenant_id=principal.tenant_id,
                student_id=principal.student_id,
            )
            try:
                audio_bytes = audio.get_or_synthesize_audio(
                    llm_gateway(request), ctx, settings, text, voice=audio.DEFAULT_VOICE
                )
                if audio_bytes and len(audio_bytes) >= 100:
                    headers = {
                        "Cache-Control": "private, max-age=86400",
                        "Content-Length": str(len(audio_bytes)),
                        "Accept-Ranges": "bytes",
                    }
                    if request.method == "HEAD":
                        return Response(content=b"", media_type="audio/mpeg", headers=headers)
                    return Response(content=audio_bytes, media_type="audio/mpeg", headers=headers)
            except Exception:
                pass

    raise ApiError(404, "podcast_not_found", "No podcast audio found for this topic yet.")


@router.post("/learn/objectives/{objective_id}/podcast")
async def upload_topic_podcast(
    objective_id: UUID,
    settings: SettingsDep,
    principal: PrincipalDep,
    file: Annotated[UploadFile, File()],
) -> dict[str, str | int]:
    """Upload a NotebookLM deep-dive MP3 audio file for this topic."""
    podcasts_dir = settings.private_content_dir / "podcasts"
    podcasts_dir.mkdir(parents=True, exist_ok=True)
    target = podcasts_dir / f"{objective_id}.mp3"
    content = await file.read()
    if len(content) < 100:
        raise ApiError(400, "invalid_audio", "Uploaded audio file is empty or too small.")
    target.write_bytes(content)
    return {"status": "ok", "url": f"/api/learn/objectives/{objective_id}/podcast", "size_bytes": len(content)}


@router.get("/learn/viva", response_model=list[VivaTopicOut])
def get_viva_topics(subject_id: UUID, principal: PrincipalDep, s: DbDep) -> list[VivaTopicOut]:
    """Topics whose approved solved exam question she can defend step by step (docs/STUDENT-APP.md §19)."""
    return service.viva_topics(s, subject_id)


@router.get("/learn/viva/{objective_id}", response_model=VivaQuestionOut)
def get_viva_question(objective_id: UUID, principal: PrincipalDep, s: DbDep) -> VivaQuestionOut:
    return service.viva_question(s, objective_id)


@router.post("/learn/viva/{objective_id}/steps/{index}", response_model=VivaStepOut)
def post_viva_step(
    objective_id: UUID, index: int, body: VivaStepIn, request: Request, principal: PrincipalDep, s: DbDep
) -> VivaStepOut:
    ctx = CallContext(request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=principal.student_id)
    return service.judge_viva_step(
        s, llm_gateway(request), ctx, principal, objective_id, index, body, now=datetime.now(UTC)
    )


@router.post("/learn/homework-photo", response_model=HomeworkPhotoOut)
def post_homework_photo(
    request: Request,
    principal: PrincipalDep,
    s: DbDep,
    photo: Annotated[UploadFile, File()],
) -> HomeworkPhotoOut:
    """Read a photo of her own homework and offer the topics it is on (docs/GO-LIVE-ENGAGEMENT.md F3).

    The photo is checked by code, passed to the gateway and dropped: it is not saved, and neither is what was
    read off it. Nothing here answers the homework — she gets topics, and picks one.
    """
    require_role(principal, "student")
    if principal.student_id is None:
        raise ApiError(403, "not_a_student", "this needs a student account")
    data = photo.file.read(homework.MAX_BYTES + 1)
    ctx = CallContext(request_id=request_id_of(request), tenant_id=principal.tenant_id, student_id=principal.student_id)
    return service.homework_photo(
        s, llm_gateway(request), ctx, student_id=principal.student_id, data=data, now=datetime.now(UTC)
    )
