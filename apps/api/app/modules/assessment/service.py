"""Question items (serving) and attempts: typed or photo answers, transcription and confirmation (AC-E3)."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.ids import uuid7
from app.core.rbac import Principal, require_role, require_student_access
from app.llm.gateway import CallContext, ImageInput, LLMGateway, LLMResult
from app.modules.assessment import examiner_reports
from app.modules.assessment.analytics import generate_diagnostic_report
from app.modules.assessment.models import (
    Assessment,
    AssessmentItem,
    Attempt,
    ExaminerInsight,
    Notebook,
    NotebookItem,
    QuestionBookmark,
    QuestionItem,
)
from app.modules.assessment.schemas import (
    AssessmentBriefOut,
    AssessmentCreate,
    AssessmentItemOut,
    AssessmentOut,
    AssessmentReportOut,
    AttemptMeta,
    AttemptOut,
    BookmarkIn,
    BookmarkOut,
    ExamFromMistakesIn,
    ExamFromNotebookIn,
    ExamFromTopicsIn,
    ExaminerInsightOut,
    ExaminerInsightsOut,
    NotebookCreate,
    NotebookItemCreate,
    NotebookItemOut,
    NotebookOut,
    NotebookUpdate,
    QuestionOut,
    ScoreOut,
    TranscriptionConfirm,
    TranscriptionOut,
)
from app.modules.audit import service as audit
from app.modules.events import service as events

STUDY_KINDS = frozenset({"baseline", "post", "retention"})
# A test she (or a parent) sets from chosen topics. Sat under exam conditions, but it is not a real paper: mastery
# does not weigh it as exam evidence and the readiness view does not count it as a past-paper sitting.
TOPIC_EXAM = "topic_exam"
# Evidence mastery weighs as exam performance: the study tests and timed past-paper sittings.
EXAM_STYLE_KINDS = frozenset({"exam_style", *STUDY_KINDS})
# Everything sat under exam conditions (AC-L5, AC-R3). While one is in progress there is no tutoring and no outside
# practice, and its marks are shown only after it is submitted.
EXAM_CONDITION_KINDS = frozenset({TOPIC_EXAM, *EXAM_STYLE_KINDS})
SELECTION_RULE = "manual_v1"  # forms are chosen by a person (PHASE-1 §5), not generated
TOPIC_SELECTION = "topics_v1"  # order_for_topics + fill_to_marks
TRANSCRIBE_ROLE = "vision_transcriber"
TRANSCRIBE_PROMPT = "answer_transcribe"


class Transcription(BaseModel):
    working: str = Field(max_length=10000)
    final_answer: str | None = Field(default=None, max_length=500)
    legibility: Literal["good", "fair", "poor"] = "fair"
    uncertain: list[str] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True)
class ItemView:
    id: UUID
    tenant_id: UUID
    subject_id: UUID
    source_ref: str | None
    stem: str
    context: str | None
    marks: int
    command_word: str | None
    has_diagram: bool
    calculator_allowed: bool | None
    objective_ids: tuple[UUID, ...]
    difficulty: int | None
    answer_spec: dict[str, Any]
    mark_scheme: dict[str, Any]
    reserved_for_study: bool
    skill_ids: tuple[UUID, ...] = ()


def _item_view(row: QuestionItem) -> ItemView:
    return ItemView(
        id=row.id,
        tenant_id=row.tenant_id,
        subject_id=row.subject_id,
        source_ref=row.source_ref,
        stem=row.stem,
        context=row.context,
        marks=row.marks,
        command_word=row.command_word,
        has_diagram=row.has_diagram,
        calculator_allowed=row.calculator_allowed,
        objective_ids=tuple(row.objective_ids or ()),
        difficulty=row.difficulty,
        answer_spec=dict(row.answer_spec or {}),
        mark_scheme=dict(row.mark_scheme or {}),
        reserved_for_study=row.reserved_for_study,
        skill_ids=tuple(row.skill_ids or ()),
    )


def servable_item(s: Session, item_id: UUID, *, allow_reserved: bool = False) -> ItemView:
    """Only verified items are served; study-reserved items only inside study assessments."""
    row = s.get(QuestionItem, item_id)
    if row is None or row.verification_status != "verified" or (row.reserved_for_study and not allow_reserved):
        raise not_found("question")
    return _item_view(row)


def question_out(item: ItemView) -> QuestionOut:
    return QuestionOut(
        id=item.id,
        subject_id=item.subject_id,
        source_ref=item.source_ref,
        context=item.context,
        stem=item.stem,
        marks=item.marks,
        command_word=item.command_word,
        has_diagram=item.has_diagram,
        calculator_allowed=item.calculator_allowed,
        objective_ids=list(item.objective_ids),
        skill_ids=list(item.skill_ids),
    )


@dataclass(frozen=True)
class AttemptView:
    id: UUID
    tenant_id: UUID
    student_id: UUID
    item: ItemView
    assessment_kind: str | None
    assessment_status: str | None
    working: str | None
    final_answer: str | None
    photo_uris: tuple[str, ...]
    transcription: str | None
    transcription_meta: dict[str, Any]
    confirmed_at: datetime | None
    pre_confidence: int | None
    max_assistance_level: int
    submitted_at: datetime

    @property
    def ready_for_marking(self) -> bool:
        return not self.photo_uris or self.confirmed_at is not None

    @property
    def working_for_marking(self) -> str | None:
        return self.transcription if self.photo_uris else self.working


def _view(s: Session, row: Attempt) -> AttemptView:
    item = s.get(QuestionItem, row.question_item_id)
    assert item is not None
    found = (
        s.execute(select(Assessment.kind, Assessment.status).where(Assessment.id == row.assessment_id)).one_or_none()
        if row.assessment_id
        else None
    )
    return AttemptView(
        id=row.id,
        tenant_id=row.tenant_id,
        student_id=row.student_id,
        item=_item_view(item),
        assessment_kind=found.kind if found else None,
        assessment_status=found.status if found else None,
        working=row.answer_text,
        final_answer=row.final_answer,
        photo_uris=tuple(row.answer_image_uris or ()),
        transcription=row.transcription,
        transcription_meta=dict(row.transcription_meta or {}),
        confirmed_at=row.transcription_confirmed_at,
        pre_confidence=row.pre_confidence,
        max_assistance_level=row.max_assistance_level,
        submitted_at=row.submitted_at,
    )


def attempt_out(view: AttemptView, evaluation_id: UUID | None) -> AttemptOut:
    if evaluation_id is not None:
        status = "evaluated"
    elif view.photo_uris and view.confirmed_at is None:
        status = "awaiting_transcription" if view.transcription is None else "awaiting_confirmation"
    else:
        status = "ready"
    meta = view.transcription_meta
    transcription = (
        TranscriptionOut(
            working=view.transcription,
            final_answer=view.final_answer,
            legibility=meta.get("legibility"),
            uncertain=list(meta.get("uncertain", [])),
            confirmed_at=view.confirmed_at,
            edited=bool(meta.get("edited", False)),
        )
        if view.photo_uris
        else None
    )
    return AttemptOut(
        id=view.id,
        question_item_id=view.item.id,
        status=status,  # type: ignore[arg-type]
        working=view.working,
        final_answer=view.final_answer,
        photo_count=len(view.photo_uris),
        transcription=transcription,
        pre_confidence=view.pre_confidence,
        max_assistance_level=view.max_assistance_level,
        submitted_at=view.submitted_at,
        evaluation_id=evaluation_id,
    )


def candidate_items(
    s: Session, *, subject_id: UUID, command_word: str | None = None, no_calculator: bool = False
) -> list[ItemView]:
    """Verified practice items for a subject. Study-reserved items are never practice candidates.

    ``command_word`` narrows the pool to one command word, for a drill (AC-R4). Command words are stored
    lower case (app.jobs.ao_tag normalises them), so the match is exact rather than case-insensitive.
    ``no_calculator`` keeps only questions from papers that forbid a calculator (an unknown rule is not "no").
    """
    query = select(QuestionItem).where(
        QuestionItem.subject_id == subject_id,
        QuestionItem.verification_status == "verified",
        QuestionItem.reserved_for_study.is_(False),
    )
    if command_word:
        query = query.where(QuestionItem.command_word == command_word.strip().lower())
    if no_calculator:
        query = query.where(QuestionItem.calculator_allowed.is_(False))
    return [_item_view(r) for r in s.scalars(query).all()]


@dataclass(frozen=True)
class ItemBrief:
    id: UUID
    origin: str
    source_ref: str | None
    marks: int
    command_word: str | None
    difficulty: int | None
    stem: str | None = None
    context: str | None = None


def items_for_objective(s: Session, objective_id: UUID) -> list[ItemBrief]:
    """Verified, non-reserved items tagged with one objective (docs/STUDENT-APP.md AC-U8), easiest first."""
    rows = s.execute(
        select(
            QuestionItem.id,
            QuestionItem.origin,
            QuestionItem.source_ref,
            QuestionItem.marks,
            QuestionItem.command_word,
            QuestionItem.difficulty,
            QuestionItem.stem,
            QuestionItem.context,
        ).where(
            QuestionItem.objective_ids.any(objective_id),
            QuestionItem.verification_status == "verified",
            QuestionItem.reserved_for_study.is_(False),
        )
    ).all()
    items = [ItemBrief(*row) for row in rows]
    return sorted(items, key=lambda i: (i.marks, i.difficulty or 3, i.source_ref or ""))


@dataclass(frozen=True)
class TopicItem:
    id: UUID
    marks: int
    objective_ids: tuple[UUID, ...]


def order_for_topics(
    items: Sequence[TopicItem], objective_ids: Sequence[UUID], *, attempted: Collection[UUID]
) -> list[UUID]:
    """The order questions on chosen topics are offered in (rule ``TOPIC_SELECTION``), pure and deterministic.

    Topics take turns in the order chosen, so one well-stocked topic cannot fill the set. Within a topic, questions
    she has not answered before come first, then the higher-mark ones, then by source; a question on several chosen
    topics is offered once, under the first of them."""
    queues: dict[UUID, list[TopicItem]] = {o: [] for o in objective_ids}
    for item in items:
        home = next((o for o in objective_ids if o in item.objective_ids), None)
        if home is not None:
            queues[home].append(item)
    for queue in queues.values():
        queue.sort(key=lambda i: (i.id in attempted, -i.marks, str(i.id)))
    out: list[UUID] = []
    while any(queues.values()):
        for queue in queues.values():
            if queue:
                out.append(queue.pop(0).id)
    return out


def fill_to_marks(order: Sequence[UUID], marks: Mapping[UUID, int], target: int) -> list[UUID]:
    """Take questions in order while they fit under the target; stop once it is reached. Never goes over."""
    chosen: list[UUID] = []
    total = 0
    for item_id in order:
        if total >= target:
            break
        if total + marks[item_id] <= target:
            chosen.append(item_id)
            total += marks[item_id]
    return chosen


def _topic_items(s: Session, subject_id: UUID, objective_ids: Sequence[UUID]) -> list[TopicItem]:
    rows = s.execute(
        select(QuestionItem.id, QuestionItem.marks, QuestionItem.objective_ids).where(
            QuestionItem.subject_id == subject_id,
            QuestionItem.objective_ids.overlap(list(objective_ids)),
            QuestionItem.verification_status == "verified",
            QuestionItem.reserved_for_study.is_(False),
        )
    ).all()
    return [TopicItem(r[0], r[1], tuple(r[2] or ())) for r in rows]


def items_for_objectives(
    s: Session, *, subject_id: UUID, objective_ids: Sequence[UUID], student_id: UUID | None, limit: int
) -> list[UUID]:
    """Practice questions on the chosen topics of one subject, in ``order_for_topics`` order."""
    items = _topic_items(s, subject_id, objective_ids)
    attempted = latest_attempts(s, student_id=student_id, item_ids=[i.id for i in items]) if student_id else {}
    return order_for_topics(items, list(dict.fromkeys(objective_ids)), attempted=attempted.keys())[:limit]


def seconds_answering_since(s: Session, *, student_id: UUID, since: datetime) -> int:
    """Time she spent on the questions she submitted since ``since``, as measured by the answer box. Answers with no
    timing (older ones) add nothing, so this never overstates."""
    total = s.scalar(
        select(func.coalesce(func.sum(Attempt.time_spent_s), 0)).where(
            Attempt.student_id == student_id, Attempt.submitted_at >= since
        )
    )
    return int(total or 0)


def latest_attempts(
    s: Session, *, student_id: UUID, item_ids: Sequence[UUID], since: datetime | None = None
) -> dict[UUID, UUID]:
    """item_id -> her latest attempt on it (since ``since``, when given)."""
    if not item_ids:
        return {}
    query = select(Attempt.question_item_id, Attempt.id).where(
        Attempt.student_id == student_id, Attempt.question_item_id.in_(list(item_ids))
    )
    if since is not None:
        query = query.where(Attempt.submitted_at >= since)
    latest: dict[UUID, UUID] = {}
    for item_id, attempt_id in s.execute(query.order_by(Attempt.submitted_at)).all():
        latest[item_id] = attempt_id  # later rows win
    return latest


@dataclass(frozen=True)
class ConfidenceAttempt:
    id: UUID
    question_item_id: UUID
    subject_id: UUID
    question_stem: str
    pre_confidence: int
    max_assistance_level: int
    submitted_at: datetime
    time_spent_s: int | None = None


def attempts_with_confidence(
    s: Session,
    *,
    student_id: UUID,
    subject_id: UUID | None = None,
    limit: int = 100,
) -> list[ConfidenceAttempt]:
    """Attempts with a student-reported pre_confidence rating, newest first."""
    query = (
        select(
            Attempt.id,
            Attempt.question_item_id,
            QuestionItem.subject_id,
            QuestionItem.stem,
            Attempt.pre_confidence,
            Attempt.max_assistance_level,
            Attempt.submitted_at,
            Attempt.time_spent_s,
        )
        .join(QuestionItem, QuestionItem.id == Attempt.question_item_id)
        .where(Attempt.student_id == student_id, Attempt.pre_confidence.is_not(None))
    )
    if subject_id is not None:
        query = query.where(QuestionItem.subject_id == subject_id)
    query = query.order_by(Attempt.submitted_at.desc()).limit(limit)
    rows = s.execute(query).all()
    return [
        ConfidenceAttempt(
            id=r[0],
            question_item_id=r[1],
            subject_id=r[2],
            question_stem=r[3],
            pre_confidence=r[4],
            max_assistance_level=r[5],
            submitted_at=r[6],
            time_spent_s=r[7],
        )
        for r in rows
    ]


def item_briefs(s: Session, item_ids: Sequence[UUID]) -> dict[UUID, ItemBrief]:
    if not item_ids:
        return {}
    rows = s.execute(
        select(
            QuestionItem.id,
            QuestionItem.origin,
            QuestionItem.source_ref,
            QuestionItem.marks,
            QuestionItem.command_word,
            QuestionItem.difficulty,
            QuestionItem.stem,
            QuestionItem.context,
        ).where(QuestionItem.id.in_(list(item_ids)))
    ).all()
    return {row[0]: ItemBrief(*row) for row in rows}


def past_paper_items(s: Session, subject_id: UUID) -> list[tuple[ItemBrief, tuple[UUID, ...]]]:
    """A subject's servable past-paper questions with the objectives they are tagged to (the past-paper hub)."""
    rows = s.execute(
        select(
            QuestionItem.id,
            QuestionItem.origin,
            QuestionItem.source_ref,
            QuestionItem.marks,
            QuestionItem.command_word,
            QuestionItem.difficulty,
            QuestionItem.stem,
            QuestionItem.context,
            QuestionItem.objective_ids,
        ).where(
            QuestionItem.subject_id == subject_id,
            QuestionItem.origin == "past_paper",
            QuestionItem.verification_status == "verified",
            QuestionItem.reserved_for_study.is_(False),
        )
    ).all()
    return [(ItemBrief(*row[:8]), tuple(row[8] or ())) for row in rows]


def item_counts_by_objective(s: Session, subject_id: UUID) -> dict[UUID, int]:
    """objective_id -> how many servable items practise it."""
    counts: dict[UUID, int] = {}
    for ids in s.scalars(
        select(QuestionItem.objective_ids).where(
            QuestionItem.subject_id == subject_id,
            QuestionItem.verification_status == "verified",
            QuestionItem.reserved_for_study.is_(False),
        )
    ):
        for objective_id in ids or ():
            counts[objective_id] = counts.get(objective_id, 0) + 1
    return counts


def recent_item_ids(s: Session, *, student_id: UUID, since: datetime) -> set[UUID]:
    return set(
        s.scalars(
            select(Attempt.question_item_id).where(Attempt.student_id == student_id, Attempt.submitted_at >= since)
        )
    )


def tested_skills(s: Session, attempt_id: UUID) -> tuple[UUID, tuple[UUID, ...]] | None:
    """(subject id, the assessment objectives its question tests) for one attempt; None if it is gone."""
    row = s.execute(
        select(QuestionItem.subject_id, QuestionItem.skill_ids)
        .join(Attempt, Attempt.question_item_id == QuestionItem.id)
        .where(Attempt.id == attempt_id)
    ).first()
    return (row[0], tuple(row[1] or ())) if row else None


def get_attempt(s: Session, principal: Principal, attempt_id: UUID) -> AttemptView:
    row = s.get(Attempt, attempt_id)
    if row is None:
        raise not_found("attempt")
    require_student_access(principal, row.student_id, "assessments")
    return _view(s, row)


def existing_attempt(s: Session, principal: Principal, meta: AttemptMeta) -> AttemptView | None:
    """Idempotent replay: the same key returns the original attempt."""
    require_role(principal, "student")
    row = s.scalar(
        select(Attempt).where(
            Attempt.student_id == principal.student_id, Attempt.idempotency_key == meta.idempotency_key
        )
    )
    if row is None:
        return None
    if row.question_item_id != meta.question_item_id:
        raise ApiError(409, "idempotency_conflict", "this idempotency key was already used for a different question")
    return _view(s, row)


def _help_level(s: Session, student_id: UUID, session_id: UUID | None) -> int:
    """Highest help level given in the session since its previous attempt (the learning engine records help)."""
    if session_id is None:
        return 0
    wanted, level = str(session_id), 0
    for ev in events.list_events(s, student_id=student_id, types=("help_given", "attempt_submitted")):
        if ev.payload.get("session_id") != wanted:
            continue
        level = 0 if ev.type == "attempt_submitted" else max(level, int(ev.payload.get("level", 0)))
    return level


def create_attempt(
    s: Session,
    principal: Principal,
    meta: AttemptMeta,
    *,
    now: datetime,
    working: str | None = None,
    final_answer: str | None = None,
    photo_uris: Sequence[str] = (),
    attempt_id: UUID | None = None,
) -> AttemptView:
    require_role(principal, "student")
    assert principal.student_id is not None
    kind: str | None = None
    if meta.assessment_id is not None:
        found = s.execute(
            select(Assessment.kind, Assessment.status, Assessment.student_id).where(Assessment.id == meta.assessment_id)
        ).one_or_none()
        if found is None or found.student_id != principal.student_id:
            raise not_found("assessment")
        if found.status == "draft":
            raise ApiError(409, "assessment_not_started", "start the test before answering")
        if found.status != "in_progress":
            raise ApiError(409, "assessment_closed", "this assessment is no longer open")
        in_form = s.scalar(
            select(AssessmentItem.position).where(
                AssessmentItem.assessment_id == meta.assessment_id,
                AssessmentItem.question_item_id == meta.question_item_id,
            )
        )
        if in_form is None:  # otherwise any open study test would unlock every reserved item
            raise ApiError(422, "item_not_in_assessment", "this question is not part of the test")
        answered = s.scalar(
            select(Attempt.id).where(
                Attempt.assessment_id == meta.assessment_id, Attempt.question_item_id == meta.question_item_id
            )
        )
        if answered is not None:
            raise ApiError(409, "already_answered", "this question has already been answered in the test")
        kind = found.kind
        if kind in EXAM_CONDITION_KINDS and meta.session_id is not None:
            raise ApiError(422, "no_session_in_test", "test answers cannot be part of a tutoring session")
    elif active_exam_assessment(s, student_id=principal.student_id) is not None:
        raise ApiError(409, "assessment_in_progress", "finish and submit your test first")
    item = servable_item(s, meta.question_item_id, allow_reserved=kind in STUDY_KINDS)
    if meta.session_id is not None:
        from app.modules.tutoring import service as tutoring  # local import: tutoring depends on assessment

        if not tutoring.session_exists(s, meta.session_id):
            raise not_found("session")
    if not photo_uris and not ((working or "").strip() or (final_answer or "").strip()):
        raise ApiError(422, "empty_answer", "write your working or a final answer")

    row = Attempt(
        id=attempt_id or uuid7(),
        tenant_id=principal.tenant_id,
        student_id=principal.student_id,
        question_item_id=item.id,
        assessment_id=meta.assessment_id,
        session_id=meta.session_id,
        idempotency_key=meta.idempotency_key,
        answer_text=working,
        final_answer=final_answer,
        answer_image_uris=list(photo_uris),
        pre_confidence=meta.pre_confidence,
        max_assistance_level=0
        if kind in EXAM_CONDITION_KINDS
        else _help_level(s, principal.student_id, meta.session_id),
        time_spent_s=meta.time_spent_s,
        submitted_at=now,
    )
    s.add(row)
    s.flush()
    common: dict[str, Any] = {
        "tenant_id": principal.tenant_id,
        "student_id": principal.student_id,
        "occurred_at": now,
        "subject_id": item.subject_id,
        "objective_ids": list(item.objective_ids),
        "ref_type": "attempt",
        "ref_id": row.id,
    }
    events.append(
        s,
        event_type="attempt_submitted",
        payload={
            "attempt_id": row.id,
            "question_item_id": item.id,
            "assessment_id": meta.assessment_id,
            "session_id": meta.session_id,
        },
        **common,
    )
    if meta.pre_confidence is not None:
        events.append(
            s,
            event_type="confidence_reported",
            payload={"confidence": meta.pre_confidence, "attempt_id": row.id},
            **common,
        )
    return _view(s, row)


# --- assessments ----------------------------------------------------------------------------------------------


# A timed paper is sat in one go. One left open longer than this (an abandoned sitting) stops holding everything
# else under exam conditions; it stays open to submit. Study tests never lapse: the study depends on them.
SITTING_HOLD = timedelta(hours=12)


def active_exam_assessment(s: Session, *, student_id: UUID, now: datetime | None = None) -> UUID | None:
    """The student's started, unsubmitted study test, or a timed past-paper sitting started within ``SITTING_HOLD``.
    While one exists all input belongs to it (ARCHITECTURE §10.1): no practice attempts and no tutoring help
    (AC-L5, AC-R3)."""
    since = (now or datetime.now(UTC)) - SITTING_HOLD
    return s.scalar(
        select(Assessment.id)
        .where(
            Assessment.student_id == student_id,
            Assessment.status == "in_progress",
            or_(
                Assessment.kind.in_(STUDY_KINDS),
                Assessment.kind.in_(("exam_style", TOPIC_EXAM)) & (Assessment.started_at >= since),
            ),
        )
        .limit(1)
    )


@dataclass(frozen=True)
class ItemMark:
    evaluation_id: UUID
    status: str  # final | needs_review | overridden
    marks_awarded: float


@dataclass(frozen=True)
class ScoreEntry:
    marks: int
    answered: bool
    mark: ItemMark | None


def _student_score(score: ScoreOut, is_student: bool) -> ScoreOut:
    """A total that includes a provisional mark is not a number she sees (AC-E6); a parent sees it."""
    if is_student and score.pending_review:
        return score.model_copy(update={"awarded": None})
    return score


def score_form(entries: Sequence[ScoreEntry], *, submitted: bool) -> ScoreOut:
    """Unanswered items score 0. A score is final only when every answer has a final or reviewed mark."""
    unmarked = sum(1 for e in entries if e.answered and e.mark is None)
    pending = sum(1 for e in entries if e.mark is not None and e.mark.status == "needs_review")
    return ScoreOut(
        awarded=sum(e.mark.marks_awarded for e in entries if e.mark is not None),
        available=sum(e.marks for e in entries),
        answered=sum(1 for e in entries if e.answered),
        unmarked=unmarked,
        pending_review=pending,
        final=submitted and unmarked == 0 and pending == 0,
    )


@dataclass(frozen=True)
class SittingItem:
    question_item_id: UUID
    objective_ids: tuple[UUID, ...]
    marks: int
    attempt_id: UUID | None


@dataclass(frozen=True)
class StudySitting:
    assessment_id: UUID
    kind: str
    form_code: str | None
    submitted_at: datetime
    items: tuple[SittingItem, ...]


def study_sittings(s: Session, *, student_id: UUID, subject_id: UUID) -> list[StudySitting]:
    """Submitted baseline/post/retention tests with each item's objectives, marks and answer (for study results)."""
    rows = s.scalars(
        select(Assessment)
        .where(
            Assessment.student_id == student_id,
            Assessment.subject_id == subject_id,
            Assessment.kind.in_(STUDY_KINDS),
            Assessment.status.in_(("submitted", "evaluated")),
            Assessment.submitted_at.is_not(None),
        )
        .order_by(Assessment.submitted_at)
    ).all()
    sittings = []
    for row in rows:
        items = s.execute(
            select(QuestionItem.id, QuestionItem.objective_ids, QuestionItem.marks)
            .join(AssessmentItem, AssessmentItem.question_item_id == QuestionItem.id)
            .where(AssessmentItem.assessment_id == row.id)
            .order_by(AssessmentItem.position)
        ).all()
        attempts = dict(
            s.execute(select(Attempt.question_item_id, Attempt.id).where(Attempt.assessment_id == row.id)).all()
        )
        assert row.submitted_at is not None
        sittings.append(
            StudySitting(
                assessment_id=row.id,
                kind=row.kind,
                form_code=row.form_code,
                submitted_at=row.submitted_at,
                items=tuple(
                    SittingItem(item_id, tuple(objectives or ()), marks, attempts.get(item_id))
                    for item_id, objectives, marks in items
                ),
            )
        )
    return sittings


def _assessment_row(s: Session, principal: Principal, assessment_id: UUID) -> Assessment:
    row = s.get(Assessment, assessment_id)
    if row is None:
        raise not_found("assessment")
    require_student_access(principal, row.student_id, "assessments")
    return row


def _require_test_taker(principal: Principal, row: Assessment) -> None:
    if principal.role != "student" or principal.student_id != row.student_id:
        raise ApiError(403, "forbidden", "only the student can take this test")


def create_assessment(
    s: Session, principal: Principal, body: AssessmentCreate, *, student_id: UUID, now: datetime
) -> UUID:
    study = body.kind in STUDY_KINDS
    if study:
        require_role(principal, "guardian", "admin")  # study forms are set by a person, never by the student
    require_student_access(principal, student_id, "assessments")
    if study and body.form_code is None:
        raise ApiError(422, "form_code_required", "study tests need a form code (A, B or C)")
    rows = {r.id: r for r in s.scalars(select(QuestionItem).where(QuestionItem.id.in_(body.question_item_ids)))}
    unusable = [
        str(item_id)
        for item_id in body.question_item_ids
        if (row := rows.get(item_id)) is None
        or row.verification_status != "verified"
        or row.subject_id != body.subject_id
        or row.reserved_for_study != study
    ]
    if unusable:
        pool = "study-reserved" if study else "practice"
        raise ApiError(
            422,
            "invalid_items",
            f"{len(unusable)} question(s) are not verified {pool} questions for this subject: {', '.join(unusable)}",
        )
    if study:
        duplicate = s.scalar(
            select(Assessment.id).where(
                Assessment.student_id == student_id,
                Assessment.subject_id == body.subject_id,
                Assessment.kind == body.kind,
                Assessment.form_code == body.form_code,
                Assessment.status != "abandoned",
            )
        )
        if duplicate is not None:
            raise ApiError(409, "duplicate_form", "this study test already exists")

    total = sum(rows[i].marks for i in body.question_item_ids)
    objective_ids = sorted({str(o) for i in body.question_item_ids for o in rows[i].objective_ids})
    assessment = Assessment(
        id=uuid7(),
        tenant_id=principal.tenant_id,
        student_id=student_id,
        subject_id=body.subject_id,
        kind=body.kind,
        form_code=body.form_code,
        status="draft",
        selection_rule_version=SELECTION_RULE,
        config={"total_marks": total, "objective_ids": objective_ids},
    )
    s.add(assessment)
    s.flush()
    for position, item_id in enumerate(body.question_item_ids):
        s.add(AssessmentItem(assessment_id=assessment.id, position=position, question_item_id=item_id))
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="assessment.created",
        entity_type="assessment",
        entity_id=assessment.id,
        student_id=student_id,
        meta={"kind": body.kind, "form_code": body.form_code, "items": len(rows), "total_marks": total},
    )
    s.flush()
    return assessment.id


def create_exam_from_topics(
    s: Session,
    principal: Principal,
    body: ExamFromTopicsIn,
    *,
    student_id: UUID,
    now: datetime,
) -> UUID:
    """A topic exam: questions on the chosen topics, up to the target marks, sat under exam conditions."""
    require_student_access(principal, student_id, "assessments")
    objective_ids = list(dict.fromkeys(body.objective_ids))
    items = _topic_items(s, body.subject_id, objective_ids)
    attempted = latest_attempts(s, student_id=student_id, item_ids=[i.id for i in items])
    order = order_for_topics(items, objective_ids, attempted=attempted.keys())
    selected_ids = fill_to_marks(order, {i.id: i.marks for i in items}, body.target_marks)
    if not selected_ids:
        # Never a paper on other topics in their place: she chose these, so say there is nothing to set.
        raise ApiError(
            422, "no_questions_for_topics", "there are no practice questions on the chosen topics yet — choose others"
        )
    marks = {i.id: i.marks for i in items}
    total = sum(marks[i] for i in selected_ids)
    assessment = Assessment(
        id=uuid7(),
        tenant_id=principal.tenant_id,
        student_id=student_id,
        subject_id=body.subject_id,
        kind=TOPIC_EXAM,
        form_code=None,
        status="draft",
        selection_rule_version=TOPIC_SELECTION,
        config={
            "title": body.title,
            "exam_category": body.exam_category,
            "duration_min": body.duration_minutes,
            "target_marks": body.target_marks,
            "total_marks": total,
            "objective_ids": [str(o) for o in objective_ids],
        },
    )
    s.add(assessment)
    s.flush()
    for position, item_id in enumerate(selected_ids):
        s.add(AssessmentItem(assessment_id=assessment.id, position=position, question_item_id=item_id))
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="assessment.created",
        entity_type="assessment",
        entity_id=assessment.id,
        student_id=student_id,
        meta={"kind": TOPIC_EXAM, "category": body.exam_category, "items": len(selected_ids), "total_marks": total},
    )
    s.flush()
    return assessment.id


def list_assessments(s: Session, principal: Principal, *, student_id: UUID) -> list[AssessmentBriefOut]:
    require_student_access(principal, student_id, "assessments")
    rows = s.scalars(
        select(Assessment).where(Assessment.student_id == student_id).order_by(Assessment.created_at.desc())
    )
    return [
        AssessmentBriefOut(
            id=r.id,
            subject_id=r.subject_id,
            kind=r.kind,
            form_code=r.form_code,
            status=r.status,
            total_marks=int((r.config or {}).get("total_marks", 0)),
            created_at=r.created_at,
            submitted_at=r.submitted_at,
            config=r.config,
        )
        for r in rows
    ]


def start_assessment(s: Session, principal: Principal, assessment_id: UUID, *, now: datetime) -> None:
    row = _assessment_row(s, principal, assessment_id)
    _require_test_taker(principal, row)
    if row.status == "in_progress":
        return
    if row.status != "draft":
        raise ApiError(409, "assessment_closed", "this assessment is no longer open")
    if row.kind in EXAM_CONDITION_KINDS and active_exam_assessment(s, student_id=row.student_id) is not None:
        raise ApiError(409, "assessment_in_progress", "finish and submit your other test first")
    row.status = "in_progress"
    row.started_at = now
    s.flush()


def submit_assessment(s: Session, principal: Principal, assessment_id: UUID, *, now: datetime) -> None:
    row = _assessment_row(s, principal, assessment_id)
    _require_test_taker(principal, row)
    if row.status in ("submitted", "evaluated"):
        return
    if row.status != "in_progress":
        raise ApiError(409, "assessment_not_started", "start the test before submitting it")
    row.status = "submitted"
    row.submitted_at = now
    s.flush()


def assessment_attempts(s: Session, principal: Principal, assessment_id: UUID) -> dict[UUID, UUID]:
    """question_item_id -> attempt_id for the test's answers."""
    _assessment_row(s, principal, assessment_id)
    rows = s.execute(select(Attempt.question_item_id, Attempt.id).where(Attempt.assessment_id == assessment_id)).all()
    return {item_id: attempt_id for item_id, attempt_id in rows}


def assessment_detail(
    s: Session, principal: Principal, assessment_id: UUID, marks: Mapping[UUID, ItemMark]
) -> AssessmentOut:
    """``marks``: attempt_id -> latest evaluation, supplied by the evaluation module (which depends on this one)."""
    row = _assessment_row(s, principal, assessment_id)
    is_student = principal.role == "student"
    submitted = row.status in ("submitted", "evaluated")
    show_questions = not (is_student and row.status == "draft")
    show_marks = not (is_student and row.kind in EXAM_CONDITION_KINDS and not submitted)
    positions = s.execute(
        select(AssessmentItem.position, AssessmentItem.question_item_id)
        .where(AssessmentItem.assessment_id == row.id)
        .order_by(AssessmentItem.position)
    ).all()
    items = {
        r.id: _item_view(r)
        for r in s.scalars(select(QuestionItem).where(QuestionItem.id.in_([p[1] for p in positions])))
    }
    attempts = dict(
        s.execute(select(Attempt.question_item_id, Attempt.id).where(Attempt.assessment_id == row.id)).all()
    )
    entries, out_items = [], []
    for position, item_id in positions:
        item = items[item_id]
        attempt_id = attempts.get(item_id)
        mark = marks.get(attempt_id) if attempt_id else None
        entries.append(ScoreEntry(marks=item.marks, answered=attempt_id is not None, mark=mark))
        out_items.append(
            AssessmentItemOut(
                position=position,
                question_item_id=item_id,
                marks=item.marks,
                question=question_out(item) if show_questions else None,
                attempt_id=attempt_id,
                evaluation_id=mark.evaluation_id if mark and show_marks else None,
                evaluation_status=mark.status if mark and show_marks else None,
                # A provisional mark is not a number she sees (AC-E6); the parent review queue has it.
                marks_awarded=mark.marks_awarded
                if mark and show_marks and not (is_student and mark.status == "needs_review")
                else None,
            )
        )
    return AssessmentOut(
        id=row.id,
        student_id=row.student_id,
        subject_id=row.subject_id,
        kind=row.kind,
        form_code=row.form_code,
        status=row.status,
        no_help=row.kind in EXAM_CONDITION_KINDS,
        total_marks=int((row.config or {}).get("total_marks", 0)),
        created_at=row.created_at,
        started_at=row.started_at,
        submitted_at=row.submitted_at,
        items=out_items,
        score=_student_score(score_form(entries, submitted=submitted), is_student) if show_marks else None,
        config=row.config,
    )


def _require_photo_owner(principal: Principal, view: AttemptView) -> None:
    if principal.role != "student" or principal.student_id != view.student_id:
        raise ApiError(403, "forbidden", "only the student can change this attempt")
    if not view.photo_uris:
        raise ApiError(409, "not_a_photo_attempt", "this attempt has no photos")


def check_can_transcribe(principal: Principal, view: AttemptView, *, evaluated: bool) -> None:
    _require_photo_owner(principal, view)
    if evaluated:
        raise ApiError(409, "already_evaluated", "this attempt has already been marked")
    if view.confirmed_at is not None:
        raise ApiError(409, "already_confirmed", "the transcription has already been confirmed")


def transcribe(
    gateway: LLMGateway, ctx: CallContext, *, stem: str, photos: Sequence[tuple[bytes, str]]
) -> LLMResult[Transcription]:
    return gateway.structured(
        TRANSCRIBE_ROLE,
        TRANSCRIBE_PROMPT,
        {"stem": stem},
        Transcription,
        ctx,
        images=[ImageInput(data, media_type) for data, media_type in photos],
    )


def save_transcription(
    s: Session, principal: Principal, attempt_id: UUID, result: LLMResult[Transcription]
) -> AttemptView:
    row = s.get(Attempt, attempt_id)
    if row is None:
        raise not_found("attempt")
    _require_photo_owner(principal, _view(s, row))
    if row.transcription_confirmed_at is not None:
        raise ApiError(409, "already_confirmed", "the transcription has already been confirmed")
    t = result.value
    row.transcription = t.working
    row.final_answer = t.final_answer
    row.transcription_meta = {
        "legibility": t.legibility,
        "uncertain": t.uncertain,
        "machine_working": t.working,
        "machine_final_answer": t.final_answer,
        "model": result.model,
        "prompt": f"{TRANSCRIBE_PROMPT}/{result.prompt_version}",
    }
    s.flush()
    return _view(s, row)


def confirm_transcription(
    s: Session, principal: Principal, attempt_id: UUID, body: TranscriptionConfirm, *, now: datetime, evaluated: bool
) -> AttemptView:
    row = s.get(Attempt, attempt_id)
    if row is None:
        raise not_found("attempt")
    _require_photo_owner(principal, _view(s, row))
    if evaluated:
        raise ApiError(409, "already_evaluated", "this attempt has already been marked")
    meta = dict(row.transcription_meta or {})
    meta["edited"] = body.working != meta.get("machine_working") or body.final_answer != meta.get(
        "machine_final_answer"
    )
    row.transcription = body.working
    row.final_answer = body.final_answer
    row.transcription_confirmed_at = now
    row.transcription_meta = meta
    s.flush()
    return _view(s, row)


# --- examiner-report insights (Phase 2, AC-R6) ------------------------------------------------------------

# Whole-paper points are general; a few beside the question's own is plenty.
MAX_PAPER_INSIGHTS = 3


def _insight_out(row: ExaminerInsight) -> ExaminerInsightOut:
    where = f"Paper {row.component}" + (f", Question {row.question_ref}" if row.question_ref else "")
    return ExaminerInsightOut(
        kind=row.kind,  # type: ignore[arg-type]
        text=row.text,
        question_ref=row.question_ref,
        component=row.component,
        exam_series=row.exam_series,
        attribution=f"{row.report_title} — {where}",
    )


def examiner_insights(s: Session, item_id: UUID) -> ExaminerInsightsOut:
    """What the examiner report for this item's own paper says about it, most specific first.

    Callers decide *when* this may be shown (evaluation service: only after the answer is marked).
    """
    item = s.get(QuestionItem, item_id)
    if item is None:
        raise not_found("question")
    if not item.source_ref or "/Q" not in item.source_ref:
        return ExaminerInsightsOut(item_ref=item.source_ref)
    refs = examiner_reports.ancestor_refs(item.source_ref)
    depth = {ref: n for n, ref in enumerate(refs)}
    rows = s.scalars(select(ExaminerInsight).where(ExaminerInsight.item_ref.in_(refs))).all()
    question = sorted(rows, key=lambda r: (depth[r.item_ref or ""], r.segment_key, r.ordinal))
    syllabus, component, series = item.source_ref.rpartition("/Q")[0].split("/")
    paper = s.scalars(
        select(ExaminerInsight)
        .where(
            ExaminerInsight.syllabus_code == syllabus,
            ExaminerInsight.component == component,
            ExaminerInsight.exam_series == series,
            ExaminerInsight.item_ref.is_(None),
        )
        .order_by((ExaminerInsight.kind != "advice"), ExaminerInsight.ordinal)
        .limit(MAX_PAPER_INSIGHTS)
    ).all()
    return ExaminerInsightsOut(
        item_ref=item.source_ref,
        question=[_insight_out(r) for r in question],
        paper=[_insight_out(r) for r in paper],
    )


def stored_insight_segments(s: Session, source_id: UUID) -> dict[str, tuple[str, str]]:
    """segment_key -> (segment_sha, prompt_version) already stored for a report, so re-runs skip them."""
    rows = s.execute(
        select(ExaminerInsight.segment_key, ExaminerInsight.segment_sha, ExaminerInsight.prompt_version)
        .where(ExaminerInsight.source_id == source_id)
        .distinct()
    ).all()
    return {key: (sha, version) for key, sha, version in rows}


def replace_segment_insights(
    s: Session,
    *,
    tenant_id: UUID,
    source_id: UUID,
    subject_id: UUID,
    report_title: str,
    exam_series: str,
    segment: examiner_reports.ReportSegment,
    points: Sequence[examiner_reports.KeptPoint],
    prompt_version: str,
    model: str,
) -> int:
    """Replace what is stored for one report segment with its newly guarded points."""
    s.execute(
        delete(ExaminerInsight).where(
            ExaminerInsight.source_id == source_id, ExaminerInsight.segment_key == segment.key
        )
    )
    for ordinal, point in enumerate(points):
        s.add(
            ExaminerInsight(
                tenant_id=tenant_id,
                source_id=source_id,
                subject_id=subject_id,
                syllabus_code=segment.syllabus_code,
                component=segment.component,
                exam_series=exam_series,
                report_title=report_title,
                question_ref=point.question_ref,
                item_ref=(
                    examiner_reports.item_ref(segment.syllabus_code, segment.component, exam_series, point.question_ref)
                    if point.question_ref
                    else None
                ),
                kind=point.kind,
                text=point.text,
                ordinal=ordinal,
                pages=list(segment.pages),
                segment_key=segment.key,
                segment_sha=segment.sha,
                segmenter_version=examiner_reports.SEGMENTER_VERSION,
                prompt_version=prompt_version,
                model=model,
            )
        )
    return len(points)


# --- bookmarks: questions she saved to revise ---------------------------------------------------------------------


def list_bookmarks(s: Session, principal: Principal, *, student_id: UUID) -> list[BookmarkOut]:
    require_student_access(principal, student_id, "assessments")
    rows = s.execute(
        select(QuestionBookmark, QuestionItem)
        .join(QuestionItem, QuestionItem.id == QuestionBookmark.question_item_id)
        .where(QuestionBookmark.student_id == student_id)
        .order_by(QuestionBookmark.created_at.desc())
    ).all()
    return [
        BookmarkOut(
            question_item_id=item.id,
            subject_id=item.subject_id,
            source_ref=item.source_ref,
            stem=item.stem,
            marks=item.marks,
            tag=mark.tag,  # type: ignore[arg-type]
            note=mark.note,
            saved_at=mark.created_at,
        )
        for mark, item in rows
        if item.verification_status == "verified" and not item.reserved_for_study  # withdrawn since, or a study item
    ]


def save_bookmark(s: Session, principal: Principal, item_id: UUID, body: BookmarkIn) -> None:
    """Save (or retag) a question she can see. Study-reserved questions cannot be saved, as they cannot be served."""
    require_role(principal, "student")
    assert principal.student_id is not None
    item = servable_item(s, item_id)
    row = s.scalar(
        select(QuestionBookmark).where(
            QuestionBookmark.student_id == principal.student_id, QuestionBookmark.question_item_id == item.id
        )
    )
    if row is None:
        row = QuestionBookmark(
            tenant_id=principal.tenant_id, student_id=principal.student_id, question_item_id=item.id, tag=body.tag
        )
        s.add(row)
    row.tag = body.tag
    row.note = (body.note or "").strip() or None
    s.flush()


def remove_bookmark(s: Session, principal: Principal, item_id: UUID) -> None:
    require_role(principal, "student")
    s.execute(
        delete(QuestionBookmark).where(
            QuestionBookmark.student_id == principal.student_id, QuestionBookmark.question_item_id == item_id
        )
    )


# ---------------------------------------------------------------------------
# Digital Notebooks
# ---------------------------------------------------------------------------


def list_notebooks(s: Session, principal: Principal, *, student_id: UUID) -> list[NotebookOut]:
    require_student_access(principal, student_id, "assessments")
    # Subquery to count items in each notebook
    item_counts = dict(
        s.execute(
            select(NotebookItem.notebook_id, func.count(NotebookItem.id))
            .where(NotebookItem.student_id == student_id)
            .group_by(NotebookItem.notebook_id)
        ).all()
    )
    rows = s.scalars(
        select(Notebook).where(Notebook.student_id == student_id).order_by(Notebook.updated_at.desc())
    ).all()
    return [
        NotebookOut(
            id=r.id,
            student_id=r.student_id,
            title=r.title,
            description=r.description,
            icon=r.icon,
            color=r.color,
            subject_id=r.subject_id,
            item_count=item_counts.get(r.id, 0),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


def get_notebook(s: Session, principal: Principal, notebook_id: UUID) -> NotebookOut:
    nb = s.get(Notebook, notebook_id)
    if nb is None:
        raise not_found("notebook")
    require_student_access(principal, nb.student_id, "assessments")
    count = s.scalar(select(func.count(NotebookItem.id)).where(NotebookItem.notebook_id == notebook_id)) or 0
    return NotebookOut(
        id=nb.id,
        student_id=nb.student_id,
        title=nb.title,
        description=nb.description,
        icon=nb.icon,
        color=nb.color,
        subject_id=nb.subject_id,
        item_count=count,
        created_at=nb.created_at,
        updated_at=nb.updated_at,
    )


def create_notebook(
    s: Session, principal: Principal, body: NotebookCreate, *, student_id: UUID, now: datetime
) -> NotebookOut:
    require_student_access(principal, student_id, "assessments")
    nb = Notebook(
        id=uuid7(),
        tenant_id=principal.tenant_id,
        student_id=student_id,
        title=body.title.strip(),
        description=body.description.strip() if body.description else None,
        icon=body.icon or "📓",
        color=body.color or "amber",
        subject_id=body.subject_id,
        created_at=now,
        updated_at=now,
    )
    s.add(nb)
    s.flush()
    return NotebookOut(
        id=nb.id,
        student_id=nb.student_id,
        title=nb.title,
        description=nb.description,
        icon=nb.icon,
        color=nb.color,
        subject_id=nb.subject_id,
        item_count=0,
        created_at=nb.created_at,
        updated_at=nb.updated_at,
    )


def update_notebook(
    s: Session, principal: Principal, notebook_id: UUID, body: NotebookUpdate, *, now: datetime
) -> NotebookOut:
    nb = s.get(Notebook, notebook_id)
    if nb is None:
        raise not_found("notebook")
    require_student_access(principal, nb.student_id, "assessments")
    if body.title is not None:
        nb.title = body.title.strip()
    if body.description is not None:
        nb.description = body.description.strip() or None
    if body.icon is not None:
        nb.icon = body.icon
    if body.color is not None:
        nb.color = body.color
    nb.updated_at = now
    s.flush()
    return get_notebook(s, principal, notebook_id)


def delete_notebook(s: Session, principal: Principal, notebook_id: UUID) -> None:
    nb = s.get(Notebook, notebook_id)
    if nb is None:
        raise not_found("notebook")
    require_student_access(principal, nb.student_id, "assessments")
    s.delete(nb)
    s.flush()


def list_notebook_items(s: Session, principal: Principal, notebook_id: UUID) -> list[NotebookItemOut]:
    nb = s.get(Notebook, notebook_id)
    if nb is None:
        raise not_found("notebook")
    require_student_access(principal, nb.student_id, "assessments")
    rows = s.execute(
        select(NotebookItem, QuestionItem)
        .join(QuestionItem, QuestionItem.id == NotebookItem.question_item_id)
        .where(NotebookItem.notebook_id == notebook_id)
        .order_by(NotebookItem.created_at.desc())
    ).all()
    return [
        NotebookItemOut(
            id=item.id,
            notebook_id=item.notebook_id,
            question_item_id=item.question_item_id,
            student_notes=item.student_notes,
            created_at=item.created_at,
            question=question_out(q),
        )
        for item, q in rows
    ]


def add_notebook_item(
    s: Session, principal: Principal, notebook_id: UUID, body: NotebookItemCreate, *, now: datetime
) -> NotebookItemOut:
    nb = s.get(Notebook, notebook_id)
    if nb is None:
        raise not_found("notebook")
    require_student_access(principal, nb.student_id, "assessments")
    q = servable_item(s, body.question_item_id)
    existing = s.scalar(
        select(NotebookItem).where(
            NotebookItem.notebook_id == notebook_id,
            NotebookItem.question_item_id == q.id,
        )
    )
    if existing is not None:
        existing.student_notes = body.student_notes
        s.flush()
        return NotebookItemOut(
            id=existing.id,
            notebook_id=existing.notebook_id,
            question_item_id=existing.question_item_id,
            student_notes=existing.student_notes,
            created_at=existing.created_at,
            question=question_out(q),
        )
    item = NotebookItem(
        id=uuid7(),
        tenant_id=principal.tenant_id,
        student_id=nb.student_id,
        notebook_id=nb.id,
        question_item_id=q.id,
        student_notes=body.student_notes,
        created_at=now,
    )
    s.add(item)
    nb.updated_at = now
    s.flush()
    return NotebookItemOut(
        id=item.id,
        notebook_id=item.notebook_id,
        question_item_id=item.question_item_id,
        student_notes=item.student_notes,
        created_at=item.created_at,
        question=question_out(q),
    )


def remove_notebook_item(s: Session, principal: Principal, notebook_id: UUID, question_item_id: UUID) -> None:
    nb = s.get(Notebook, notebook_id)
    if nb is None:
        raise not_found("notebook")
    require_student_access(principal, nb.student_id, "assessments")
    s.execute(
        delete(NotebookItem).where(
            NotebookItem.notebook_id == notebook_id,
            NotebookItem.question_item_id == question_item_id,
        )
    )
    s.flush()


def create_exam_from_notebook(
    s: Session,
    principal: Principal,
    body: ExamFromNotebookIn,
    *,
    student_id: UUID,
    now: datetime,
) -> UUID:
    """Create a timed custom practice assessment directly from questions saved in a notebook."""
    require_student_access(principal, student_id, "assessments")
    nb = s.get(Notebook, body.notebook_id)
    if nb is None:
        raise not_found("notebook")
    items = s.scalars(
        select(NotebookItem).where(NotebookItem.notebook_id == body.notebook_id).order_by(NotebookItem.created_at.asc())
    ).all()
    if not items:
        raise ApiError(422, "empty_notebook", "This notebook contains no questions yet — add questions first.")

    q_ids = [it.question_item_id for it in items]
    questions = s.scalars(select(QuestionItem).where(QuestionItem.id.in_(q_ids))).all()
    q_map = {q.id: q for q in questions}
    total_marks = sum(q_map[qid].marks for qid in q_ids if qid in q_map)

    # Pick subject: from notebook if set, or from the first question
    subject_id = nb.subject_id or (questions[0].subject_id if questions else None)
    if subject_id is None:
        raise ApiError(422, "unknown_subject", "Cannot determine subject for notebook exam.")

    assessment = Assessment(
        id=uuid7(),
        tenant_id=principal.tenant_id,
        student_id=student_id,
        subject_id=subject_id,
        kind="topic_exam",
        form_code=None,
        status="draft",
        selection_rule_version="notebook_v1",
        config={
            "title": body.title,
            "notebook_id": str(body.notebook_id),
            "duration_min": body.duration_minutes,
            "total_marks": total_marks,
        },
    )
    s.add(assessment)
    s.flush()
    for position, qid in enumerate(q_ids):
        if qid in q_map:
            s.add(AssessmentItem(assessment_id=assessment.id, position=position, question_item_id=qid))
    s.flush()
    return assessment.id


def create_exam_from_mistakes(
    s: Session,
    principal: Principal,
    body: ExamFromMistakesIn,
    *,
    student_id: UUID,
    now: datetime,
) -> UUID:
    """Generate a targeted 'Kill the Mistake' retry drill on unresolved mistake objectives."""
    require_student_access(principal, student_id, "assessments")
    from app.modules.mistakes import service as mistakes_service

    open_mistakes = mistakes_service.list_mistakes(s, student_id=student_id, subject_id=body.subject_id, status="open")
    if not open_mistakes:
        open_mistakes = mistakes_service.list_mistakes(
            s, student_id=student_id, subject_id=body.subject_id, status="improving"
        )
    if not open_mistakes:
        raise ApiError(422, "no_open_mistakes", "Great news! You have no open or recurring mistakes in this subject.")

    objective_ids = [m.objective_id for m in open_mistakes if m.objective_id is not None]
    if not objective_ids:
        raise ApiError(422, "no_mistake_objectives", "Open mistakes do not have linked curriculum objectives.")

    selected_ids = items_for_objectives(
        s,
        subject_id=body.subject_id,
        objective_ids=objective_ids,
        student_id=student_id,
        limit=body.limit,
    )
    if not selected_ids:
        raise ApiError(422, "no_practice_items", "No fresh practice items found for your open mistake objectives.")

    questions = [servable_item(s, qid) for qid in selected_ids]
    total_marks = sum(q.marks for q in questions)

    assessment = Assessment(
        id=uuid7(),
        tenant_id=principal.tenant_id,
        student_id=student_id,
        subject_id=body.subject_id,
        kind="topic_exam",
        form_code=None,
        status="draft",
        selection_rule_version="mistakes_drill_v1",
        config={
            "title": body.title,
            "duration_min": body.duration_minutes,
            "total_marks": total_marks,
            "drill_type": "mistakes_killer",
        },
    )
    s.add(assessment)
    s.flush()
    for position, qid in enumerate(selected_ids):
        s.add(AssessmentItem(assessment_id=assessment.id, position=position, question_item_id=qid))
    s.flush()
    return assessment.id


def get_assessment_report(
    s: Session,
    principal: Principal,
    assessment_id: UUID,
) -> AssessmentReportOut:
    """Generate the full deterministic performance diagnostic report for an assessment."""
    assessment = s.get(Assessment, assessment_id)
    if assessment is None:
        raise not_found("assessment")
    require_student_access(principal, assessment.student_id, "assessments")
    report = generate_diagnostic_report(s, assessment_id, assessment.student_id)
    return AssessmentReportOut(
        assessment_id=report.assessment_id,
        title=report.title,
        kind=report.kind,
        total_questions=report.total_questions,
        total_marks_available=report.total_marks_available,
        total_marks_awarded=report.total_marks_awarded,
        score_percentage=report.score_percentage,
        pacing=report.pacing,  # type: ignore[arg-type]
        time_sinks=report.time_sinks,  # type: ignore[arg-type]
        topic_breakdown=report.topic_breakdown,  # type: ignore[arg-type]
        difficulty_breakdown=report.difficulty_breakdown,  # type: ignore[arg-type]
        mistake_types_summary=report.mistake_types_summary,
        action_plan=report.action_plan,
    )
