"""Learn: streams → subjects → chapters → topic pages (docs/STUDENT-APP.md).

Orchestration only. Curriculum, mastery, the question bank, mistakes and retrieval are read through their own
services; what is new here is the stored lesson and the checks it passes (``lessons``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.llm.gateway import CallContext, LLMGateway, LLMResult
from app.modules.assessment import service as assessment
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.schemas import SubjectOut, TopicNode, TopicRef
from app.modules.enrollment import service as enrollment
from app.modules.evaluation import service as evaluation
from app.modules.events import service as events
from app.modules.external_training import service as external_training
from app.modules.identity import service as identity
from app.modules.knowledge import service as knowledge
from app.modules.learn import crucible, diagrams, exam, homework, labels, lessons, pacing, viva
from app.modules.learn.models import Lesson
from app.modules.learn.schemas import (
    ChapterOut,
    ClassLogOut,
    ConnectionOut,
    CrucibleOut,
    CruciblePerspectiveOut,
    DiagramOut,
    ExamAnswerOut,
    ExamLevelOut,
    ExternalLessonOut,
    GroundOut,
    HomeworkMatchOut,
    HomeworkPhotoOut,
    HowExaminedOut,
    ItemCardOut,
    KeyTermOut,
    LessonOut,
    LessonSectionOut,
    LessonTableOut,
    MistakeCardOut,
    ObjectiveCardOut,
    PastPaperChapterOut,
    PastPaperItemOut,
    PastPapersOut,
    PodcastDialogueTurnOut,
    SourceRefOut,
    StepOut,
    StreamOut,
    SubjectCardOut,
    SubjectLearnOut,
    TopicOut,
    VivaQuestionOut,
    VivaStepIn,
    VivaStepOut,
    VivaTopicOut,
    WalkStepOut,
    WorkedExamOut,
    WorkedExampleOut,
)
from app.modules.mastery import service as mastery
from app.modules.mistakes import service as mistakes
from app.modules.safety import service as safety
from app.modules.studies import service as studies
from app.modules.subjects import service as subjects
from app.tools.dates import local_date

SCOPE = "mastery"
LESSON_ROLE = "lesson_writer"
LESSON_PROMPT = "lesson_write"
# The version lessons are written with: v4 (exam standard, examples rising to exam level), switched on 21 Sep 2026
# after the pilot (docs/STUDENT-APP.md §15); v5 (revision notes: definitions, bullets, tables, model exam answers)
# on 22 Sep 2026 (§21); v6 (coaching center framework + NotebookLM podcast) in Oct 2026.
LESSON_PROMPT_VERSION = "v6"
ILLUSTRATE_ROLE = "lesson_illustrator"
ILLUSTRATE_PROMPT = "lesson_illustrate"
WALK_ROLE = "exam_walker"
WALK_PROMPT = "exam_walkthrough"
VIVA_ROLE = "viva_judge"
VIVA_PROMPT = "viva_judge"
CRUCIBLE_ROLE = "crucible_writer"
CRUCIBLE_PROMPT = "crucible_write"
CRUCIBLE_MIN_MARKS = 10
MAX_DIAGRAMS = 3
EXCERPTS = 10  # v5 notes cover the whole objective
TABLE_EXCERPTS = 3  # the book's own tables on it, added beside the searched excerpts
CHECK_YOURSELF = 3
EXAM_QUESTIONS = 50
SCHOOL_LED_NOTICE = (
    "This topic is being learnt at school for now, as part of the study you agreed to. "
    "Its lesson and practice open here after the study's retention test."
)
NOT_TAUGHT_NOTICE = "Scholr knows this syllabus but does not teach it yet, so there is no lesson or practice here."
EXTERNAL_NOTICE = (
    "You learn this in your IIT Foundation classes. Scholr doesn't teach it again — it shows the IGCSE ground "
    "underneath, warms you up before class, and keeps a record of how your classes went."
)
LESSONS_ONLY_NOTICE = (
    "Scholr explains this topic from your course book and the Tutor will answer your doubts on it. It doesn't "
    "set or mark questions here yet, so practise from the book's end-of-chapter questions."
)
WARM_UP = 3


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def _levels(s: Session, student_id: UUID | None) -> dict[UUID, int]:
    if student_id is None:
        return {}
    return {row.objective_id: row.level for row in mastery.list_mastery(s, student_id=student_id)}


def _card(subject: SubjectOut, objective_ids: Sequence[UUID], levels: dict[UUID, int]) -> SubjectCardOut:
    seen = [levels[o] for o in objective_ids if o in levels]
    return SubjectCardOut(
        id=subject.id,
        code=subject.code,
        name=subject.name,
        syllabus_code=subject.syllabus_code,
        stage=subject.stage,  # type: ignore[arg-type]
        objectives=len(objective_ids),
        secure=sum(1 for level in seen if level >= mastery.MasteryLevel.COMPETENT) if seen else None,
        practised=len(seen),
    )


def objective_ids(nodes: Sequence[TopicNode]) -> list[UUID]:
    out: list[UUID] = []
    for node in nodes:
        out.extend(o.id for o in node.objectives)
        out.extend(objective_ids(node.children))
    return out


def streams(s: Session, *, student_id: UUID | None) -> list[StreamOut]:
    by_code = {subject.code: subject for subject in curriculum.list_subjects(s)}
    levels = _levels(s, student_id)
    out = []
    for stream in subjects.load_streams().streams:
        cards = []
        for config in subjects.subjects_in_stream(stream.key):
            subject = by_code.get(config.subject_code)
            if subject is None:  # configured but not seeded yet
                continue
            tree = curriculum.subject_tree(s, subject.id)
            cards.append(_card(subject, objective_ids(tree.topics) if tree else [], levels))
        out.append(
            StreamOut(
                key=stream.key, name=stream.name, description=stream.description, status=stream.status, subjects=cards
            )
        )
    return out


def _lesson_states(s: Session, objective_ids: Sequence[UUID]) -> dict[UUID, str]:
    if not objective_ids:
        return {}
    rows = s.execute(select(Lesson.objective_id, Lesson.status).where(Lesson.objective_id.in_(list(objective_ids))))
    return dict(rows.all())  # type: ignore[arg-type]


def _objective_card(
    objective_id: UUID,
    code: str,
    statement: str,
    *,
    levels: dict[UUID, int],
    items: dict[UUID, int],
    lesson_states: dict[UUID, str],
    school_led: set[UUID],
    classes: dict[UUID, tuple[int, bool]] | None = None,
) -> ObjectiveCardOut:
    level = levels.get(objective_id)
    seen, hard = (classes or {}).get(objective_id, (0, False))
    return ObjectiveCardOut(
        id=objective_id,
        code=code,
        statement=statement,
        mastery_level=level,
        mastery_name=mastery.LEVEL_NAMES[level] if level is not None else None,
        items=items.get(objective_id, 0),
        lesson=lesson_states.get(objective_id, "none"),  # type: ignore[arg-type]
        school_led=objective_id in school_led,
        classes=seen,
        struggled=hard,
    )


def subject_view(s: Session, subject_id: UUID, *, student_id: UUID | None, now: datetime) -> SubjectLearnOut:
    tree = curriculum.subject_tree(s, subject_id)
    if tree is None:
        raise not_found("subject")
    config = subjects.config_for(tree.subject.code)
    levels = _levels(s, student_id)
    all_ids = objective_ids(tree.topics)
    items = assessment.item_counts_by_objective(s, subject_id)
    lesson_states = _lesson_states(s, all_ids)
    school_led = studies.control_objective_ids(s, student_id=student_id, at=now) if student_id else set()
    classes = (
        external_training.lesson_counts(s, student_id=student_id, subject_id=subject_id)
        if student_id and config.stage == "external"
        else {}
    )

    def chapter(node: TopicNode) -> ChapterOut:
        return ChapterOut(
            id=node.id,
            code=node.code,
            name=node.name,
            objectives=[
                _objective_card(
                    o.id,
                    o.code,
                    o.statement,
                    levels=levels,
                    items=items,
                    lesson_states=lesson_states,
                    school_led=school_led,
                    classes=classes,
                )
                for o in node.objectives
            ],
            chapters=[chapter(child) for child in node.children],
        )

    return SubjectLearnOut(
        subject=_card(tree.subject, all_ids, levels),
        stream=config.path,
        chapters=[chapter(node) for node in tree.topics],
    )


# ---------------------------------------------------------------------------
# Topic page
# ---------------------------------------------------------------------------


def _lesson_out(row: Lesson) -> LessonOut:
    content = row.content or {}

    def refs(sources: list[dict]) -> list[SourceRefOut]:
        seen: dict[tuple[str, int | None], SourceRefOut] = {}
        for src in sources:
            page = src.get("page") if (src.get("page") or 0) >= 1 else None  # front matter has no printed page
            seen.setdefault((src["title"], page), SourceRefOut(title=src["title"], page=page))
        return list(seen.values())

    podcast_audio_url = content.get("podcast_audio_url") or None
    if not podcast_audio_url:
        from app.core.config import get_settings

        podcasts_dir = get_settings().private_content_dir / "podcasts"
        if (podcasts_dir / f"{row.objective_id}.mp3").exists():
            podcast_audio_url = f"/api/learn/objectives/{row.objective_id}/podcast"

    return LessonOut(
        id=row.id,
        status=row.status,  # type: ignore[arg-type]
        summary=content.get("summary", ""),
        introduction=content.get("introduction", ""),
        podcast_audio_url=podcast_audio_url,
        podcast_script=[
            PodcastDialogueTurnOut(speaker=turn.get("speaker", "Host"), text=turn.get("text", ""))
            for turn in content.get("podcast_script", [])
        ],
        sections=[
            LessonSectionOut(
                heading=x["heading"],
                body=x["body"],
                definition=x.get("definition", ""),
                points=x.get("points", []),
                exam_tip=x.get("exam_tip", ""),
                mental_model=x.get("mental_model", ""),
                formula_notes=x.get("formula_notes", ""),
                sources=refs(x["sources"]),
            )
            for x in content.get("sections", [])
        ],
        tables=[
            LessonTableOut(
                title=x["title"],
                columns=x["columns"],
                rows=x["rows"],
                section=x.get("section", 0),
                sources=refs(x["sources"]),
            )
            for x in content.get("tables", [])
        ],
        exam_answers=[
            ExamAnswerOut(question=x["question"], points=x["points"], sources=refs(x["sources"]))
            for x in content.get("exam_answers", [])
        ],
        key_terms=[KeyTermOut(term=x["term"], meaning=x["meaning"]) for x in content.get("key_terms", [])],
        worked_examples=[
            WorkedExampleOut(
                problem=x["problem"],
                strategy=x.get("strategy", ""),
                steps=x["steps"],
                final_answer=x["final_answer"],
                unit=x.get("unit") or None,
                checked=x.get("checked"),
                coaching_takeaway=x.get("coaching_takeaway", ""),
                sources=refs(x.get("sources", [])),
                level=x.get("level") or None,
                section=x.get("section", 0),
            )
            for x in content.get("worked_examples", [])
        ],
        # Only approved diagrams reach her (AC-U14): a candidate nobody has looked at is not study material.
        diagrams=[
            DiagramOut(kind=d["kind"], caption=d["caption"], data=d["data"], sections=d.get("sections", []))
            for d in content.get("diagrams", [])
            if d.get("approved")
        ],
        pitfalls=content.get("pitfalls", []),
        generated_at=row.generated_at,
    )


def _item_card(
    item: assessment.ItemBrief,
    *,
    last_status: str | None = None,
    last_marks: float | None = None,
) -> ItemCardOut:
    return ItemCardOut(
        id=item.id,
        source_ref=item.source_ref,
        label=labels.item_label(item.source_ref, item.origin),
        marks=item.marks,
        command_word=item.command_word,
        stem=item.stem,
        context=item.context,
        difficulty=item.difficulty,
        origin=item.origin,
        last_status=last_status,  # type: ignore[arg-type]
        last_marks=last_marks,
    )


def topic_view(s: Session, objective_id: UUID, *, student_id: UUID | None, now: datetime) -> TopicOut:
    detail = curriculum.objective_detail(s, objective_id)
    if detail is None:
        raise not_found("objective")
    subject = next(x for x in curriculum.list_subjects(s) if x.id == detail.subject_id)
    config = subjects.config_for(subject.code)
    levels = _levels(s, student_id)
    school_led = studies.control_objective_ids(s, student_id=student_id, at=now) if student_id else set()
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    items = assessment.items_for_objective(s, objective_id)
    card = _objective_card(
        objective_id,
        detail.code,
        detail.statement,
        levels=levels,
        items={objective_id: len(items)},
        lesson_states={objective_id: row.status} if row else {},
        school_led=school_led,
    )
    tree = curriculum.subject_tree(s, subject.id)
    subject_card = _card(subject, objective_ids(tree.topics) if tree else [], levels)
    related = [
        ConnectionOut(
            objective_id=r.objective_id,
            objective_code=r.objective_code,
            statement=r.objective_statement,
            subject_name=r.subject_name,
            concept=r.concept_name,
            practicable=_taught(r.subject_code),
        )
        for r in curriculum.related_across_subjects(s, objective_id)
    ]
    out = TopicOut(
        objective=card,
        subject=subject_card,
        path=_path(detail.topic_path),
        lesson=None,
        lesson_available=False,
        connections=related,
    )
    if config.stage == "external":
        out.notice = EXTERNAL_NOTICE
        out.external = _external_lesson(s, objective_id, student_id=student_id, now=now, school_led=school_led)
        return out
    if not config.explains:
        out.notice = NOT_TAUGHT_NOTICE
        return out
    if card.school_led:
        out.notice = SCHOOL_LED_NOTICE
        return out
    out.lesson_available = True
    out.lesson = _lesson_out(row) if row else None
    if not config.taught_here:  # lessons-only: explained from the book and open to doubts, but no questions
        out.tutor_available = True
        out.notice = LESSONS_ONLY_NOTICE
        _add_steps(s, out, row=row, student_id=student_id, objective_id=objective_id)
        return out
    out.tutor_available = True
    out.crucible = _crucible(s, row, items) if config.pedagogy.debates else None
    out.exam_level = _exam_level(s, row, items, solves=config.pedagogy.worked_example_check == "sympy")
    worked_id = out.exam_level.worked.item_id if out.exam_level and out.exam_level.worked else None
    # The worked exam question is solved on the page, so it is not also offered to her as one to try.
    items = [i for i in items if i.id != worked_id]
    past = [i for i in items if i.origin == "past_paper"]
    other = [i for i in items if i.origin != "past_paper"]
    attempts = (
        assessment.latest_attempts(s, student_id=student_id, item_ids=[i.id for i in items])
        if student_id is not None and items
        else {}
    )
    marks_by_attempt = evaluation.marks_for_attempts(s, list(attempts.values())) if attempts else {}

    def _card_with_status(brief: assessment.ItemBrief) -> ItemCardOut:
        attempt_id = attempts.get(brief.id)
        mark = marks_by_attempt.get(attempt_id) if attempt_id else None
        status = (
            None
            if attempt_id is None
            else "answered"
            if mark is None
            else ("provisional" if mark.status == "needs_review" else "marked")
        )
        return _item_card(brief, last_status=status, last_marks=mark.marks_awarded if mark else None)

    # Check yourself: short items first; past-paper parts fill in when the bank has nothing else.
    out.check_yourself = [_card_with_status(i) for i in (other or past)[:CHECK_YOURSELF]]
    shown = {c.id for c in out.check_yourself}
    out.exam_questions = [_card_with_status(i) for i in past if i.id not in shown][:EXAM_QUESTIONS]
    if student_id is not None:
        out.mistakes = [
            MistakeCardOut(description=m.description, occurrences=m.occurrences, status=m.status)
            for m in mistakes.list_mistakes(s, student_id=student_id, subject_id=subject.id)
            if m.objective_id == objective_id
        ]
    _add_steps(s, out, row=row, student_id=student_id, objective_id=objective_id)
    return out


def _crucible(s: Session, row: Lesson | None, items: Sequence[assessment.ItemBrief]) -> CrucibleOut | None:
    stored = ((row.content or {}) if row else {}).get("crucible")
    if not stored or not stored.get("approved"):
        return None
    brief = next((i for i in items if str(i.id) == stored.get("item_id")), None)
    if brief is None:
        return None  # the question left the bank
    item = assessment.servable_item(s, brief.id)
    return CrucibleOut(
        question=_item_card(brief),
        stem=item.stem,
        perspectives=[
            CruciblePerspectiveOut(
                perspective=p["perspective"],
                sociologist=p.get("sociologist", ""),
                argument=p["argument"],
                key_concept=p.get("key_concept", ""),
                evidence=p.get("evidence", ""),
                sources=[
                    SourceRefOut(title=title, page=page)
                    for title, page in dict.fromkeys((x["title"], x.get("page")) for x in p.get("sources", []))
                ],
            )
            for p in stored["perspectives"]
        ],
        questions=list(stored.get("questions", [])),
    )


def _exam_level(
    s: Session, row: Lesson | None, items: Sequence[assessment.ItemBrief], *, solves: bool
) -> ExamLevelOut | None:
    """How the topic is examined, and the stored worked exam question when its item is still in the bank (AC-U16)."""
    how = exam.how_examined(items)
    stored = ((row.content or {}) if row else {}).get("exam")
    worked = None
    # Only a walkthrough a person has read reaches her (AC-U16), and only while its question is still in the bank.
    if stored and stored.get("approved") and any(str(i.id) == stored.get("item_id") for i in items):
        item = assessment.servable_item(s, UUID(stored["item_id"]))
        worked = WorkedExamOut(
            item_id=item.id,
            label=labels.item_label(item.source_ref, "past_paper"),
            context=item.context,
            stem=item.stem,
            marks=item.marks,
            has_diagram=item.has_diagram,
            steps=[WalkStepOut(text=x["text"], mark=x.get("mark", "")) for x in stored.get("steps", [])],
            final_answer=stored.get("final_answer", ""),
            tip=stored.get("tip") or None,
        )
    if how is None and worked is None:
        return None
    return ExamLevelOut(
        solves=solves,
        how_examined=HowExaminedOut(**how.__dict__) if how else None,
        worked=worked,
        examiner=assessment.examiner_insights(s, worked.item_id) if worked else None,
    )


HOMEWORK_UNREADABLE = (
    "I couldn't read that photo. Try again in better light, with the page flat and the writing in focus."
)
HOMEWORK_NO_MATCH = (
    "I couldn't tell which topic this is from your own books. Open the subject and pick the topic yourself — "
    "everything on the topic page works the same."
)


def homework_photo(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    student_id: UUID,
    data: bytes,
    now: datetime,
) -> HomeworkPhotoOut:
    """Read a photo of her homework and offer the topics it is on, for her to confirm (F3).

    The reader transcribes the questions; which topic it is comes from matching that text against her own books
    (`knowledge.topics_for_text`), held to the bar lessons use. A topic the validation study is keeping at school
    is left out (AC-P2), as are subjects Scholr does not explain. Nothing is stored: not the photo, not the text.
    """
    read = homework.read_photo(gateway, ctx, data=data)
    if not read.readable:
        return HomeworkPhotoOut(read=False, text_preview="", state="NONE", matches=[], notice=HOMEWORK_UNREADABLE)

    found = knowledge.topics_for_text(
        s, gateway, ctx, text=read.text, subject_ids=_explained_subject_ids(s, student_id)
    )
    school_led = studies.control_objective_ids(s, student_id=student_id, at=now)
    wanted = [m for m in found.matches if m.objective_id not in school_led]
    summaries = curriculum.objective_summaries(s, [m.objective_id for m in wanted])
    names = {x.id: x.name for x in curriculum.subject_summaries(s, [m.subject_id for m in wanted]).values()}
    matches = [
        HomeworkMatchOut(
            objective_id=m.objective_id,
            code=summaries[m.objective_id].code,
            statement=summaries[m.objective_id].statement,
            subject_id=m.subject_id,
            subject_name=names.get(m.subject_id, ""),
            similarity=m.similarity,
        )
        for m in wanted
        if m.objective_id in summaries
    ]
    return HomeworkPhotoOut(
        read=True,
        text_preview=homework.preview(read.text),
        state=found.state,  # type: ignore[arg-type]
        matches=matches,
        notice=None if matches else HOMEWORK_NO_MATCH,
    )


def _explained_subject_ids(s: Session, student_id: UUID) -> list[UUID]:
    """The subjects she is enrolled in that Scholr explains — the only corpora her photo is matched against.

    Identifying which topic a page is on has to look across her subjects, so the boundary is kept where it
    matters instead: only topic names come back, never a line of any book (PRINCIPLES §7).
    """
    enrolled = {e.subject_id for e in enrollment.list_enrollments(s, [student_id])}
    out = []
    for subject in curriculum.subject_summaries(s, list(enrolled)).values():
        try:
            if subjects.config_for(subject.code).explains:
                out.append(subject.id)
        except subjects.SubjectConfigError:
            continue
    return out


def next_part(s: Session, objective_id: UUID, *, student_id: UUID, now: datetime) -> tuple[str, int, list[str]] | None:
    """The next part of this topic page she has not done: its name, its minutes, and the parts after it.

    Read through the same view the page itself is built from, so a door that offers a topic and the page it opens
    can never disagree about how long a part takes (pacing.py, AC-U13). None for a topic with nothing left, or
    one that is not taught, school-led or has no lesson yet.

    A part rather than the whole page, because the whole page is not a session: on her own record (25 Oct 2026)
    Sociology 1.1.1 had 124 minutes left on it, which is two hours, not the half hour the long door is for.
    """
    out = topic_view(s, objective_id, student_id=student_id, now=now)
    left = [step for step in out.steps if not step.done]
    if not left:
        return None
    return left[0].label, left[0].minutes, [step.label for step in left[1:]]


def _add_steps(s: Session, out: TopicOut, *, row: Lesson | None, student_id: UUID | None, objective_id: UUID) -> None:
    """What the page is made of and how long it takes (pacing.py, AC-U13), with her own record for `done`."""
    lesson_read = False
    answered: set[UUID] = set()
    if student_id is not None:
        lesson_read = bool(
            events.list_events(s, student_id=student_id, types=["explanation_viewed"], objective_ids=[objective_id])
        )
        item_ids = [card.id for card in (*out.check_yourself, *out.exam_questions)]
        answered = set(assessment.latest_attempts(s, student_id=student_id, item_ids=item_ids))
    worked = out.exam_level.worked if out.exam_level else None
    steps = pacing.steps(
        lesson=(row.content or {}) if row and row.status == "ready" else None,
        worked_marks=worked.marks if worked else 0,
        lesson_read=lesson_read,
        check_marks=sum(card.marks for card in out.check_yourself),
        check_answered=any(card.id in answered for card in out.check_yourself),
        exam_marks=sum(card.marks for card in out.exam_questions),
        exam_answered=any(card.id in answered for card in out.exam_questions),
    )
    out.steps = [StepOut(key=x.key, label=x.label, minutes=x.minutes, done=x.done) for x in steps]
    out.minutes = pacing.total_minutes(steps)
    out.opens_on = pacing.opens_on(steps)


def _external_lesson(
    s: Session, objective_id: UUID, *, student_id: UUID | None, now: datetime, school_led: set[UUID]
) -> ExternalLessonOut:
    """An IIT lesson (docs/STUDENT-APP.md step 5, PHASE-3 §1): her logged classes on it, the IGCSE ground under it
    she is not yet secure in, and a short warm-up from that ground. It never teaches the lesson itself."""
    if student_id is None:
        return ExternalLessonOut()
    today = local_date(now, identity.student_timezone(s, student_id))
    classes = [
        ClassLogOut(
            occurred_on=log.occurred_on,
            kind=log.kind,
            title=log.title,
            score=log.score,
            max_score=log.max_score,
            struggled=struggled,
        )
        for log, struggled in external_training.logs_for_lesson(s, student_id=student_id, objective_id=objective_id)
    ]
    ground = [
        GroundOut(
            objective_id=g.objective_id,
            objective_code=g.objective_code,
            statement=g.objective_statement,
            subject_name=g.subject_name,
            concept=g.concept,
            depth=g.depth,
            practicable=g.practicable,
            reason=g.reason,
        )
        for g in external_training.ground_under(s, student_id=student_id, objective_id=objective_id, today=today)
    ]
    warm_up: list[ItemCardOut] = []
    for g in ground:
        if len(warm_up) >= WARM_UP:
            break
        if not g.practicable or g.objective_id in school_led:
            continue
        chosen = {w.id for w in warm_up}  # one question can be tagged to two of the objectives underneath
        fresh = [i for i in assessment.items_for_objective(s, g.objective_id) if i.id not in chosen]
        if fresh:
            warm_up.append(_item_card(fresh[0]))
    return ExternalLessonOut(classes=classes, ground=ground, warm_up=warm_up)


def _path(topics: Sequence[TopicRef]) -> list[str]:
    """Chapter names from the top down, without a chapter repeating its area's name ("Number › Number")."""
    names: list[str] = []
    for topic in topics:
        if not names or names[-1] != topic.name:
            names.append(topic.name)
    return names


# ---------------------------------------------------------------------------
# Past-paper hub (step 4)
# ---------------------------------------------------------------------------

_SERIES_MONTH = {"FM": 3, "MJ": 6, "ON": 11}


def _series_key(series: str | None) -> tuple[int, int]:
    """Newest first: "MJ25" before "ON24" before "MJ24"."""
    if not series or len(series) != 4 or not series[2:].isdigit():
        return (0, 0)
    return (int(series[2:]), _SERIES_MONTH.get(series[:2], 0))


def _parts(source_ref: str | None) -> tuple[str | None, str | None, str | None]:
    """ "0580/21/MJ25/Q3(a)" -> ("MJ25", "21", "3(a)")."""
    bits = (source_ref or "").split("/")
    if len(bits) != 4 or not bits[3].startswith("Q"):
        return None, None, None
    return bits[2], bits[1], bits[3][1:]


def _question_key(ref: str | None) -> tuple[int, str]:
    number = "".join(ch for ch in (ref or "").split("(")[0] if ch.isdigit())
    return (int(number) if number else 0, ref or "")


def past_papers(s: Session, subject_id: UUID, *, student_id: UUID | None, now: datetime) -> PastPapersOut:
    """Every servable past-paper question in a subject, under the chapter its first topic belongs to, newest
    series first, with her latest try. Study-reserved questions and school-led study topics are left out."""
    tree = curriculum.subject_tree(s, subject_id)
    if tree is None:
        raise not_found("subject")
    levels = _levels(s, student_id)
    card = _card(tree.subject, objective_ids(tree.topics), levels)
    if not subjects.config_for(tree.subject.code).taught_here:
        return PastPapersOut(subject=card, chapters=[], series=[], total=0, attempted=0)

    chapter_of: dict[UUID, TopicNode] = {}
    order: list[TopicNode] = []

    def walk(nodes: Sequence[TopicNode]) -> None:
        for node in nodes:
            if node.objectives:
                order.append(node)
                chapter_of.update({o.id: node for o in node.objectives})
            walk(node.children)

    walk(tree.topics)
    school_led = studies.control_objective_ids(s, student_id=student_id, at=now) if student_id else set()
    items = [(b, oids) for b, oids in assessment.past_paper_items(s, subject_id) if not set(oids) & school_led]
    attempts = (
        assessment.latest_attempts(s, student_id=student_id, item_ids=[b.id for b, _ in items]) if student_id else {}
    )
    marks = evaluation.marks_for_attempts(s, list(attempts.values()))

    grouped: dict[UUID | None, list[PastPaperItemOut]] = {}
    for brief, oids in items:
        chapter = next((chapter_of[o] for o in oids if o in chapter_of), None)
        series, paper, question = _parts(brief.source_ref)
        attempt_id = attempts.get(brief.id)
        mark = marks.get(attempt_id) if attempt_id else None
        status = (
            None
            if attempt_id is None
            else "answered"
            if mark is None
            else ("provisional" if mark.status == "needs_review" else "marked")
        )
        grouped.setdefault(chapter.id if chapter else None, []).append(
            PastPaperItemOut(
                id=brief.id,
                source_ref=brief.source_ref,
                series=series,
                paper=paper,
                question=question,
                marks=brief.marks,
                command_word=brief.command_word,
                last_status=status,
                last_marks=mark.marks_awarded if mark else None,
            )
        )

    def sort(entries: list[PastPaperItemOut]) -> list[PastPaperItemOut]:
        return sorted(
            entries,
            key=lambda x: (tuple(-v for v in _series_key(x.series)), x.paper or "", _question_key(x.question)),
        )

    chapters = [
        PastPaperChapterOut(id=node.id, code=node.code, name=node.name, items=sort(grouped[node.id]))
        for node in order
        if node.id in grouped
    ]
    if None in grouped:
        chapters.append(
            PastPaperChapterOut(id=None, code="", name="Not tagged to a topic yet", items=sort(grouped[None]))
        )
    all_series = sorted(
        {x.series for x in (i for c in chapters for i in c.items) if x.series}, key=_series_key, reverse=True
    )
    return PastPapersOut(
        subject=card,
        chapters=chapters,
        series=all_series,
        total=len(items),
        attempted=len(attempts),
    )


def _taught(subject_code: str) -> bool:
    try:
        return subjects.config_for(subject_code).taught_here
    except subjects.SubjectConfigError:
        return False


# ---------------------------------------------------------------------------
# Writing a lesson: prepare (transaction) → write (no transaction) → record (transaction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedLesson:
    tenant_id: UUID
    subject_id: UUID
    objective_id: UUID
    retrieval_state: str
    excerpts: list[lessons.Excerpt]
    corpus_key: str
    variables: dict[str, str]
    example_check: str
    names_need_citation: bool
    answer_units: bool = False
    past_papers: tuple[str, ...] = ()  # the questions examples may not copy


def _corpus_key(excerpts: Sequence[lessons.Excerpt]) -> str:
    digest = hashlib.sha256()
    for excerpt in excerpts:
        digest.update(excerpt.chunk_id.encode())
        digest.update(excerpt.text.encode())
    return digest.hexdigest()


def _format_excerpts(excerpts: Sequence[lessons.Excerpt]) -> str:
    return "\n\n".join(
        f"[{n}] {e.source_title}" + (f", p. {e.page}" if e.page else "") + f"\n{e.text}"
        for n, e in enumerate(excerpts, start=1)
    )


EXAMINED = 5


def _question_text(item: exam.ExamItem) -> str:
    return " ".join(f"{item.context or ''} {item.stem}".split())


def _examined(s: Session, objective_id: UUID) -> list[tuple[str, str]]:
    """(label, question) for the hardest past-paper questions on an objective, for the lesson writer to aim at."""
    past = [i for i in exam_items(s, objective_id) if i.origin == "past_paper"]
    past.sort(key=lambda i: (-i.marks, i.source_ref or ""))
    return [
        (f"{labels.item_label(i.source_ref, i.origin)}, {i.marks} marks", _question_text(i)) for i in past[:EXAMINED]
    ]


def prepare_lesson(
    s: Session, gateway: LLMGateway, ctx: CallContext, objective_id: UUID, *, rewrite: bool = False
) -> PreparedLesson | Lesson:
    """Retrieval and prompt variables for one lesson, or the stored lesson when there is one.

    ``rewrite`` prepares a new lesson even when one is stored; ``record_lesson`` then replaces it in place, so a
    failed rewrite leaves the old lesson where it was.
    """
    existing = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    if existing is not None and not rewrite:
        return existing
    detail = curriculum.objective_detail(s, objective_id)
    if detail is None:
        raise not_found("objective")
    config = subjects.config_for(detail.subject_code)
    if not isinstance(config, subjects.ExplainedSubjectConfig):
        raise ApiError(409, "subject_not_taught", NOT_TAUGHT_NOTICE)
    subject = curriculum.subject_summaries(s, [detail.subject_id])[detail.subject_id]
    chapter = " › ".join(p.name for p in detail.topic_path)
    result = knowledge.search(
        s,
        gateway,
        ctx,
        query=f"{chapter}: {detail.statement}",
        subject_id=detail.subject_id,
        objective_ids=[objective_id],
        k=EXCERPTS,
    )
    # Plus the book's own tables on the objective: a lesson's tables must be built from them (lesson v5).
    found = {c.id for c in result.chunks}
    tables = [
        c
        for c in knowledge.objective_tables(s, subject_id=detail.subject_id, objective_id=objective_id)
        if c.id not in found
    ][:TABLE_EXCERPTS]
    excerpts = [
        lessons.Excerpt(str(c.id), c.source_title, c.printed_page if (c.printed_page or 0) >= 1 else None, c.content)
        for c in [*result.chunks, *tables]
        if c.content_kind != "question"
    ]
    examined = _examined(s, objective_id) if isinstance(config, subjects.TaughtSubjectConfig) else []
    return PreparedLesson(
        tenant_id=ctx.tenant_id,
        subject_id=detail.subject_id,
        objective_id=objective_id,
        retrieval_state=result.state,
        excerpts=excerpts,
        corpus_key=_corpus_key(excerpts),
        variables={
            "subject": subject.name,
            "chapter": chapter,
            "objective_code": detail.code,
            "objective": detail.statement,
            "excerpts": _format_excerpts(excerpts),
            # The prompt holds the wording for each check; the subject config only says which one applies.
            "example_check": config.pedagogy.worked_example_check,
            "answer_units": "required" if config.pedagogy.answer_units else "not used",
            "examined": "\n".join(f"- ({label}) {question}" for label, question in examined)
            or "No past-paper questions on this objective are in her bank yet.",
        },
        example_check=config.pedagogy.worked_example_check,
        names_need_citation=bool(config.retrieval.citation_required_for),
        answer_units=config.pedagogy.answer_units,
        past_papers=tuple(question for _, question in examined),
    )


@dataclass(frozen=True)
class WrittenLesson:
    status: str
    content: dict
    checks: dict
    prompt_version: str | None
    model: str | None


def write_lesson(
    gateway: LLMGateway,
    ctx: CallContext,
    prepared: PreparedLesson,
    *,
    prompt_version: str = LESSON_PROMPT_VERSION,
    models: Sequence[str] | None = None,
) -> WrittenLesson:
    """No model call unless the material is good enough (AC-U3): no silent fallback to general knowledge.

    ``prompt_version`` and ``models`` exist for the lesson pilot, which writes with a new prompt (or screens a
    model) without storing anything."""
    if prepared.retrieval_state not in lessons.GROUNDED_STATES or not prepared.excerpts:
        return WrittenLesson("not_enough_material", {}, {"retrieval_state": prepared.retrieval_state}, None, None)
    result = gateway.structured(
        LESSON_ROLE,
        LESSON_PROMPT,
        prepared.variables,
        lessons.LessonDraft,
        ctx,
        prompt_version=prompt_version,
        models=models,
    )
    return finish_lesson(prepared, result)


def needs_writing(prepared: PreparedLesson) -> bool:
    """Whether the material is good enough to ask a model at all (AC-U3)."""
    return prepared.retrieval_state in lessons.GROUNDED_STATES and bool(prepared.excerpts)


def finish_lesson(prepared: PreparedLesson, result: LLMResult[lessons.LessonDraft]) -> WrittenLesson:
    """The guard, applied to a draft however it was written — live, or in a batch."""
    guarded = lessons.guard(
        result.value,
        prepared.excerpts,
        example_check=prepared.example_check,  # type: ignore[arg-type]
        names_need_citation=prepared.names_need_citation,
        answer_units=prepared.answer_units,
        past_papers=prepared.past_papers,
    )
    checks = {**guarded.report.as_dict(), "retrieval_state": prepared.retrieval_state, "cost_usd": result.cost_usd}
    if not guarded.usable:
        return WrittenLesson("not_enough_material", {}, checks, result.prompt_version, result.model)
    return WrittenLesson("ready", guarded.content(), checks, result.prompt_version, result.model)


@dataclass(frozen=True)
class Illustrated:
    """The diagrams kept for one lesson, and what happened to the rest."""

    diagrams: list[dict]
    checks: dict
    prompt_version: str | None
    model: str | None


def illustrate_lesson(
    s: Session, gateway: LLMGateway | None, ctx: CallContext | None, row: Lesson, *, subject_code: str
) -> Illustrated:
    """Add diagrams to a lesson that is already written (AC-U14). Its text is never touched.

    The model picks from the subject's own vocabulary and supplies numbers; `diagrams.check` computes the
    figure and throws out anything that does not hold up, so a wrong picture cannot reach her.
    """
    config = subjects.explained_config_for(subject_code)
    content = row.content or {}
    sections = content.get("sections", [])
    detail = curriculum.objective_detail(s, row.objective_id)
    # Which pictures belong on THIS objective is a curated decision in the subject config, not a model's
    # judgement (AC-U14). A topic with no vocabulary is skipped before any call is made.
    allowed = config.pedagogy.diagrams_for(detail.code) if detail and config and config.pedagogy else set()
    if not allowed or row.status != "ready" or not sections:
        return Illustrated([], {"skipped": "no vocabulary" if not allowed else "no lesson", "kept": 0}, None, None)
    subject = next((x for x in curriculum.list_subjects(s) if x.code == subject_code), None)
    variables = {
        "subject": subject.name if subject else subject_code,
        "objective": detail.statement if detail else "",
        "objective_code": detail.code if detail else "",
        "vocabulary": diagrams.vocabulary(sorted(allowed)),
        "max_diagrams": str(MAX_DIAGRAMS),
        "lesson": _lesson_for_prompt(content),
    }
    if gateway is None:  # a batch job: it wants the prompt, and calls finish_illustration with the reply
        return Illustrated([], {"variables": variables, "allowed": sorted(allowed)}, None, None)
    result = gateway.structured(ILLUSTRATE_ROLE, ILLUSTRATE_PROMPT, variables, lessons.DiagramDrafts, ctx)
    return finish_illustration(row, result, allowed=allowed)


def finish_illustration(row: Lesson, result: LLMResult[lessons.DiagramDrafts], *, allowed: set[str]) -> Illustrated:
    """The diagram checks, applied to a reply however it was written — live, or in a batch."""
    sections = (row.content or {}).get("sections", [])
    kept, report = lessons.guard_diagrams(result.value.diagrams, sections, allowed=allowed, limit=MAX_DIAGRAMS)
    return Illustrated(kept, {**report, "cost_usd": result.cost_usd}, result.prompt_version, result.model)


def _lesson_for_prompt(content: dict) -> str:
    """The stored lesson as the illustrator sees it: numbered sections, then the worked examples' problems."""
    lines = [f"Summary: {content.get('summary', '')}".strip()]
    for i, section in enumerate(content.get("sections", []), start=1):
        lines.append(f"{i}. {section.get('heading', '')}: {section.get('body', '')}")
    for example in content.get("worked_examples", []):
        answer = f"{example.get('final_answer', '')} {example.get('unit', '')}".strip()
        lines.append(f"Worked example: {example.get('problem', '')} -> {answer}")
    return "\n".join(line for line in lines if line.strip())


def _diagram_key(diagram: dict) -> str:
    """What makes two candidates the same picture: the kind, its figures and its caption."""
    return json.dumps(
        {"kind": diagram.get("kind"), "data": diagram.get("data"), "caption": diagram.get("caption")}, sort_keys=True
    )


def record_diagrams(
    s: Session, row: Lesson, illustrated: Illustrated, *, actor: Principal | None, now: datetime
) -> Lesson:
    """Store the kept diagrams beside the lesson text, leaving every other part of it as it was.

    A candidate identical to one already approved keeps its approval: running the job again must not quietly
    un-approve a picture a person has already looked at, nor show one nobody has.
    """
    content = dict(row.content or {})
    approved = {_diagram_key(d) for d in content.get("diagrams", []) if d.get("approved")}
    content["diagrams"] = [
        {**d, "approved": d.get("approved", False) or _diagram_key(d) in approved} for d in illustrated.diagrams
    ]
    row.content = content
    row.checks = {
        **(row.checks or {}),
        "diagrams": illustrated.checks,
        "diagram_prompt_version": illustrated.prompt_version,
        "diagram_model": illustrated.model,
        "diagram_kinds": [d["kind"] for d in illustrated.diagrams],
        "illustrated_at": now.isoformat(),
    }
    s.flush()
    audit.record(
        s,
        tenant_id=row.tenant_id,
        actor_user_id=actor.user_id if actor else None,
        actor_role=actor.role if actor else "system",
        action="learn.lesson_illustrated",
        entity_type="lesson",
        entity_id=row.id,
        meta={"kinds": [d["kind"] for d in illustrated.diagrams], "model": illustrated.model},
    )
    return row


def record_lesson(
    s: Session, prepared: PreparedLesson, written: WrittenLesson, *, actor: Principal | None, now: datetime
) -> Lesson:
    row = s.scalar(select(Lesson).where(Lesson.objective_id == prepared.objective_id))
    if row is None:
        row = Lesson(tenant_id=prepared.tenant_id, subject_id=prepared.subject_id, objective_id=prepared.objective_id)
        s.add(row)
    kept = {
        k: row.content[k]
        for k in ("exam", "crucible", "diagrams", "podcast_audio_url")
        if row.content and row.content.get(k)
    }
    if "diagrams" in kept and written.content.get("sections"):
        max_sec = len(written.content["sections"]) - 1
        kept["diagrams"] = [
            {**d, "sections": [min(max(0, idx), max_sec) for idx in d.get("sections", [0])]} for d in kept["diagrams"]
        ]
    row.status = written.status
    row.retrieval_state = prepared.retrieval_state
    # The worked exam question does not depend on the lesson text, so a rewrite keeps it.
    row.content = {**written.content, **kept}
    row.source_chunk_ids = [UUID(e.chunk_id) for e in prepared.excerpts]
    row.corpus_key = prepared.corpus_key
    row.checks = written.checks
    row.guard_version = lessons.GUARD_VERSION
    row.prompt_version = written.prompt_version
    row.model = written.model
    row.generated_at = now
    s.flush()
    audit.record(
        s,
        tenant_id=prepared.tenant_id,
        actor_user_id=actor.user_id if actor else None,
        actor_role=actor.role if actor else "system",
        action="learn.lesson_written",
        entity_type="lesson",
        entity_id=row.id,
        meta={"status": written.status, "prompt_version": written.prompt_version, "model": written.model},
    )
    return row


# ---------------------------------------------------------------------------
# The worked exam question (AC-U16): pick (transaction) → write (no transaction) → record (transaction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedWalkthrough:
    objective_id: UUID
    item: exam.ExamItem
    variables: dict[str, str]


def exam_items(s: Session, objective_id: UUID) -> list[exam.ExamItem]:
    """The servable bank items on one objective, as the exam module sees them."""
    out = []
    for brief in assessment.items_for_objective(s, objective_id):
        item = assessment.servable_item(s, brief.id)
        out.append(
            exam.ExamItem(
                id=str(item.id),
                source_ref=item.source_ref,
                origin=brief.origin,
                stem=item.stem,
                context=item.context,
                marks=item.marks,
                command_word=item.command_word,
                has_diagram=item.has_diagram,
                answer_spec=item.answer_spec,
                mark_scheme=item.mark_scheme,
            )
        )
    return out


def prepare_walkthrough(s: Session, objective_id: UUID) -> PreparedWalkthrough | None:
    """The question to solve for one objective, or None: the subject's answers cannot be checked by code (its
    worked examples are not SymPy-checked — Sociology), or no past-paper item on it qualifies."""
    detail = curriculum.objective_detail(s, objective_id)
    if detail is None:
        raise not_found("objective")
    config = subjects.config_for(detail.subject_code)
    if not isinstance(config, subjects.TaughtSubjectConfig) or config.pedagogy.worked_example_check != "sympy":
        return None
    item = exam.pick_worked(exam_items(s, objective_id))
    if item is None:
        return None
    return PreparedWalkthrough(
        objective_id=objective_id,
        item=item,
        variables={
            "marks": str(item.marks),
            "paper": labels.item_label(item.source_ref, "past_paper"),
            "context": item.context or "",
            "stem": item.stem,
            "scheme": exam.scheme_text(item),
            "marks_allowed": exam.marks_allowed(item),
            # Algebra is done by code, not asked of the model: for a graph question, the line to draw.
            "computed": f"the straight line to draw is ${line}$" if (line := exam.line_to_draw(item)) else "nothing",
        },
    )


@dataclass(frozen=True)
class WrittenWalkthrough:
    content: dict | None
    checks: dict
    prompt_version: str | None
    model: str | None


def write_walkthrough(gateway: LLMGateway, ctx: CallContext, prepared: PreparedWalkthrough) -> WrittenWalkthrough:
    result = gateway.structured(WALK_ROLE, WALK_PROMPT, prepared.variables, exam.WalkthroughDraft, ctx)
    return finish_walkthrough(prepared, result)


def finish_walkthrough(prepared: PreparedWalkthrough, result: LLMResult[exam.WalkthroughDraft]) -> WrittenWalkthrough:
    """The guard, applied to a walkthrough however it was written — live, or in a batch."""
    content, report = exam.guard_walkthrough(result.value, prepared.item)
    checks = {**report.as_dict(), "source_ref": prepared.item.source_ref, "cost_usd": result.cost_usd}
    return WrittenWalkthrough(content, checks, result.prompt_version, result.model)


def record_walkthrough(
    s: Session, objective_id: UUID, written: WrittenWalkthrough, *, actor: Principal | None, now: datetime
) -> bool:
    """Store a kept walkthrough beside the objective's lesson. A walkthrough that failed its check replaces
    nothing. Returns whether one was stored (there must be a lesson row to hold it)."""
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    if row is None or written.content is None:
        return False
    row.content = {
        **(row.content or {}),
        "exam": {
            **written.content,
            "prompt_version": written.prompt_version,
            "model": written.model,
            "written_at": now.isoformat(),
        },
    }
    s.flush()
    audit.record(
        s,
        tenant_id=row.tenant_id,
        actor_user_id=actor.user_id if actor else None,
        actor_role=actor.role if actor else "system",
        action="learn.exam_walkthrough_written",
        entity_type="lesson",
        entity_id=row.id,
        meta={"source_ref": written.content.get("source_ref"), "model": written.model},
    )
    return True


def decide_walkthrough(s: Session, objective_id: UUID, *, approved: bool, actor: Principal | None) -> bool:
    """A person's decision on a stored walkthrough: approve it (she sees it) or reject it (it is deleted)."""
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    walk = (row.content or {}).get("exam") if row else None
    if row is None or not walk:
        return False
    content = dict(row.content)
    if approved:
        content["exam"] = {**walk, "approved": True}
    else:
        content.pop("exam")
    row.content = content
    s.flush()
    audit.record(
        s,
        tenant_id=row.tenant_id,
        actor_user_id=actor.user_id if actor else None,
        actor_role=actor.role if actor else "system",
        action="learn.exam_walkthrough_approved" if approved else "learn.exam_walkthrough_rejected",
        entity_type="lesson",
        entity_id=row.id,
        meta={"source_ref": walk.get("source_ref")},
    )
    return True


def lesson_out(row: Lesson) -> LessonOut:
    return _lesson_out(row)


def recheck_stored(s: Session, subject_id: UUID) -> dict[str, int]:
    """Bring stored lessons up to the current guard without a model call, where the new guard only repairs or
    removes (v2 added the name rule, v3 the LaTeX repair). A lesson left with no section becomes
    not_enough_material."""
    config = subjects.config_for(next(x.code for x in curriculum.list_subjects(s) if x.id == subject_id))
    names_need_citation = isinstance(config, subjects.TaughtSubjectConfig) and bool(
        config.retrieval.citation_required_for
    )
    counts = {"checked": 0, "repaired": 0, "changed": 0, "emptied": 0, "parts_removed": 0}
    rows = s.scalars(
        select(Lesson).where(
            Lesson.subject_id == subject_id, Lesson.status == "ready", Lesson.guard_version != lessons.GUARD_VERSION
        )
    ).all()
    for row in rows:
        counts["checked"] += 1
        repaired, changed = lessons.repair_content(row.content)
        if changed:
            counts["repaired"] += 1
            row.content = repaired
        cleaned, removed = lessons.drop_garbled(row.content)
        if removed:
            counts["changed"] += 1
            counts["parts_removed"] += removed
            row.content = cleaned
        solved, removed = lessons.drop_unsolved(row.content)
        if removed:
            counts["changed"] += 1
            counts["examples_unsolved"] = counts.get("examples_unsolved", 0) + removed
            counts["parts_removed"] += removed
            row.content = solved
        if names_need_citation:
            texts = {str(k): v for k, v in knowledge.chunk_texts(s, list(row.source_chunk_ids)).items()}
            content, removed = lessons.recheck_names(row.content, texts)
            if removed:
                counts["changed"] += 1
                counts["parts_removed"] += removed
                row.content = content
        if not row.content.get("sections"):
            row.status = "not_enough_material"
            counts["emptied"] += 1
        row.checks = {**(row.checks or {}), "rechecked_to": lessons.GUARD_VERSION}
        row.guard_version = lessons.GUARD_VERSION
    return counts


def delete_lesson(s: Session, objective_id: UUID) -> bool:
    """Remove a stored lesson so the next request writes it again (job: prompt or corpus changed)."""
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    if row is None:
        return False
    s.delete(row)
    return True


def record_read(s: Session, principal: Principal, objective_id: UUID, *, now: datetime) -> None:
    """She read the lesson (AC-U7). Only the student's own reading is an event; a parent looking is not."""
    if principal.role != "student" or principal.student_id is None:
        return
    require_student_access(principal, principal.student_id, SCOPE)
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id, Lesson.status == "ready"))
    if row is None:
        raise not_found("lesson")
    event = events.append(
        s,
        tenant_id=principal.tenant_id,
        student_id=principal.student_id,
        event_type="explanation_viewed",
        occurred_at=now,
        payload={"lesson_id": row.id},
        subject_id=row.subject_id,
        objective_ids=[objective_id],
        ref_type="lesson",
        ref_id=row.id,
    )
    mastery.project(s, [event], tenant_id=principal.tenant_id, now=now)


# ---------------------------------------------------------------------------
# Viva: defend each step of an approved solved exam question (docs/STUDENT-APP.md §19)
# ---------------------------------------------------------------------------


def _approved_walkthrough(s: Session, objective_id: UUID) -> tuple[Lesson, dict] | None:
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    walk = (row.content or {}).get("exam") if row else None
    return (row, walk) if row and walk and walk.get("approved") and walk.get("steps") else None


def viva_topics(s: Session, subject_id: UUID) -> list[VivaTopicOut]:
    """Topics with an approved walkthrough, in syllabus order: only a person-approved solution is a fair reference."""
    tree = curriculum.subject_tree(s, subject_id)
    out = []
    for node in tree.topics if tree else []:
        for objective in _all_objectives(node):
            found = _approved_walkthrough(s, objective.id)
            if found is None:
                continue
            _, walk = found
            item = assessment.servable_item(s, UUID(walk["item_id"]))
            out.append(
                VivaTopicOut(
                    objective_id=objective.id,
                    code=objective.code,
                    statement=objective.statement,
                    label=labels.item_label(item.source_ref, "past_paper"),
                    marks=item.marks,
                    steps=len(walk["steps"]),
                )
            )
    return out


def _all_objectives(node: TopicNode) -> list:  # type: ignore[type-arg]
    return [*node.objectives, *(o for child in node.children for o in _all_objectives(child))]


def viva_question(s: Session, objective_id: UUID) -> VivaQuestionOut:
    found = _approved_walkthrough(s, objective_id)
    detail = curriculum.objective_detail(s, objective_id)
    if found is None or detail is None:
        raise not_found("viva question")
    _, walk = found
    item = assessment.servable_item(s, UUID(walk["item_id"]))
    return VivaQuestionOut(
        objective_id=objective_id,
        code=detail.code,
        statement=detail.statement,
        label=labels.item_label(item.source_ref, "past_paper"),
        marks=item.marks,
        steps=len(walk["steps"]),
        context=item.context,
        stem=item.stem,
        has_diagram=item.has_diagram,
    )


def judge_viva_step(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    principal: Principal,
    objective_id: UUID,
    index: int,
    body: VivaStepIn,
    *,
    now: datetime,
) -> VivaStepOut:
    """Judge her explanation of step `index` (1-based) against that step of the approved walkthrough, check the
    verdict in code (learn.viva), and record it as her self-explanation. Her words go through the safety pipeline
    first, as anything she types to the Tutor does."""
    if principal.role != "student" or principal.student_id is None:
        raise ApiError(403, "students_only", "Only the student defends her own working.")
    found = _approved_walkthrough(s, objective_id)
    if found is None:
        raise not_found("viva question")
    row, walk = found
    steps = walk["steps"]
    if not 1 <= index <= len(steps):
        raise not_found("viva step")
    step = steps[index - 1]
    reveal = {"step_text": step["text"], "step_mark": step.get("mark", ""), "last": index == len(steps)}
    outcome = safety.check_input(
        s, gateway, ctx, tenant_id=principal.tenant_id, student_id=principal.student_id, text=body.explanation, now=now
    )
    if outcome.blocks_tutoring:
        return VivaStepOut(verdict="safety", safety_message=outcome.response, last=reveal["last"])
    item = assessment.servable_item(s, UUID(walk["item_id"]))
    result = gateway.structured(
        VIVA_ROLE,
        VIVA_PROMPT,
        {
            "marks": str(item.marks),
            "question": " ".join(f"{item.context or ''} {item.stem}".split()),
            "shown": "\n".join(f"{n}. {x['text']}" for n, x in enumerate(steps[: index - 1], start=1)) or "(none yet)",
            "step_number": str(index),
            "step_mark": step.get("mark") or "no mark on its own",
            "reference": step["text"],
            "explanation": body.explanation,
        },
        viva.VivaJudgement,
        ctx,
    )
    # The question and the steps already shown: their numbers are hers to use, not secrets.
    known = " ".join([item.context or "", item.stem, *(x["text"] for x in steps[: index - 1])])
    judged = viva.guard(
        result.value,
        explanation=body.explanation,
        step_text=step["text"],
        later_steps=[x["text"] for x in steps[index:]],
        known=known,
    )
    events.append(
        s,
        tenant_id=principal.tenant_id,
        student_id=principal.student_id,
        event_type="self_explanation_given",
        occurred_at=now,
        payload={"source": "viva", "item_id": item.id, "step": index, "verdict": judged.verdict},
        subject_id=row.subject_id,
        objective_ids=[objective_id],
    )
    return VivaStepOut(
        verdict=judged.verdict,
        what_was_right=judged.what_was_right,
        missing=judged.missing,
        hint=judged.hint,
        **reveal,
    )


@dataclass(frozen=True)
class ApprovedWalkthrough:
    """A person-approved solved exam question (AC-U16), for features that build on one: the viva, Bug Hunter."""

    objective_id: UUID
    code: str
    statement: str
    subject_id: UUID
    item_id: UUID
    source_ref: str | None
    label: str
    context: str | None
    stem: str
    marks: int
    steps: tuple[dict, ...]
    final_answer: str


def approved_walkthroughs(s: Session, subject_id: UUID | None = None) -> list[ApprovedWalkthrough]:
    query = select(Lesson)
    if subject_id is not None:
        query = query.where(Lesson.subject_id == subject_id)
    out = []
    for row in s.scalars(query).all():
        walk = (row.content or {}).get("exam")
        if not walk or not walk.get("approved") or not walk.get("steps"):
            continue
        detail = curriculum.objective_detail(s, row.objective_id)
        try:
            item = assessment.servable_item(s, UUID(walk["item_id"]))
        except ApiError:
            continue  # the question left the bank since it was solved
        if detail is None:
            continue
        out.append(
            ApprovedWalkthrough(
                objective_id=row.objective_id,
                code=detail.code,
                statement=detail.statement,
                subject_id=row.subject_id,
                item_id=item.id,
                source_ref=item.source_ref,
                label=labels.item_label(item.source_ref, "past_paper"),
                context=item.context,
                stem=item.stem,
                marks=item.marks,
                steps=tuple(walk["steps"]),
                final_answer=walk.get("final_answer", ""),
            )
        )
    return sorted(out, key=lambda w: [int(p) if p.isdigit() else p for p in w.code.split(".")])


# ---------------------------------------------------------------------------
# The Crucible (learn/crucible.py): perspectives on a real essay question, from her coursebook
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreparedCrucible:
    objective_id: UUID
    item_id: UUID
    excerpts: list[lessons.Excerpt]
    variables: dict[str, str]


def prepare_crucible(s: Session, gateway: LLMGateway, ctx: CallContext, objective_id: UUID) -> PreparedCrucible | None:
    """The topic's highest-mark essay question and the coursebook excerpts on it, or None: the subject has no
    debates in its config, there is no essay question on the topic, or the book does not cover it well enough."""
    detail = curriculum.objective_detail(s, objective_id)
    if detail is None:
        raise not_found("objective")
    config = subjects.config_for(detail.subject_code)
    if not isinstance(config, subjects.ExplainedSubjectConfig) or not config.pedagogy.debates:
        return None
    essays = [i for i in assessment.items_for_objective(s, objective_id) if i.marks >= CRUCIBLE_MIN_MARKS]
    if not essays:
        return None
    brief = max(essays, key=lambda i: (i.marks, i.source_ref or ""))
    item = assessment.servable_item(s, brief.id)
    result = knowledge.search(
        s, gateway, ctx, query=item.stem, subject_id=detail.subject_id, objective_ids=[objective_id], k=10
    )
    if result.state not in lessons.GROUNDED_STATES:
        return None  # not enough in her book to stand behind: no debate rather than an ungrounded one
    excerpts = [
        lessons.Excerpt(str(c.id), c.source_title, c.printed_page if (c.printed_page or 0) >= 1 else None, c.content)
        for c in result.chunks
        if c.content_kind != "question"
    ]
    return PreparedCrucible(
        objective_id=objective_id,
        item_id=item.id,
        excerpts=excerpts,
        variables={"marks": str(item.marks), "question": item.stem, "excerpts": _format_excerpts(excerpts)},
    )


def finish_crucible(prepared: PreparedCrucible, result: LLMResult[crucible.CrucibleDraft]) -> tuple[dict | None, dict]:
    content, report = crucible.guard(result.value, prepared.excerpts)
    if content is not None:
        content = {
            **content,
            "item_id": str(prepared.item_id),
            "approved": False,  # a person reads it first
            "prompt_version": result.prompt_version,
            "model": result.model,
        }
    return content, report


def record_crucible(s: Session, objective_id: UUID, content: dict, *, now: datetime) -> bool:
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    if row is None:
        return False
    row.content = {**(row.content or {}), "crucible": {**content, "written_at": now.isoformat()}}
    s.flush()
    audit.record(
        s,
        tenant_id=row.tenant_id,
        actor_user_id=None,
        actor_role="system",
        action="learn.crucible_written",
        entity_type="lesson",
        entity_id=row.id,
        meta={"item_id": content.get("item_id"), "model": content.get("model")},
    )
    return True


def decide_crucible(s: Session, objective_id: UUID, *, approved: bool) -> bool:
    """A person's decision on a stored debate: approve it (she sees it) or reject it (it is deleted)."""
    row = s.scalar(select(Lesson).where(Lesson.objective_id == objective_id))
    stored = (row.content or {}).get("crucible") if row else None
    if row is None or not stored:
        return False
    content = dict(row.content)
    if approved:
        content["crucible"] = {**stored, "approved": True}
    else:
        content.pop("crucible")
    row.content = content
    s.flush()
    audit.record(
        s,
        tenant_id=row.tenant_id,
        actor_user_id=None,
        actor_role="system",
        action="learn.crucible_approved" if approved else "learn.crucible_rejected",
        entity_type="lesson",
        entity_id=row.id,
        meta={"item_id": stored.get("item_id")},
    )
    return True
