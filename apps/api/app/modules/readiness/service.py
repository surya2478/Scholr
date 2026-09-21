"""Exam readiness: where she stands against the way the exam is actually weighted (Phase 2, AC-R1..R4).

Composes other modules on request and stores nothing. Evidence is the same as everywhere else — final or
reviewed evaluations replayed from `learning_event` — so readiness cannot disagree with mastery.

No LLM anywhere in this module.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.assessment import service as assessment
from app.modules.assessment.models import Assessment, AssessmentItem, Attempt, QuestionItem
from app.modules.assessment.schemas import AssessmentCreate
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import LearningObjective, Topic
from app.modules.enrollment import service as enrollment
from app.modules.events import service as events
from app.modules.mastery import service as mastery
from app.modules.mastery.rules import MasteryLevel
from app.modules.readiness import rules
from app.modules.readiness.schemas import (
    CommandWordOut,
    PastPaperOut,
    ReadinessOut,
    SittingIn,
    SittingOut,
    SkillReadinessOut,
    TopicReadinessOut,
)
from app.modules.subjects import service as subjects

SCOPE = "progress"
EVENT_TYPES = ("attempt_evaluated", "evaluation_overridden")
# Command words with fewer answers than this are listed but never called weak.
MIN_COMMAND_WORD_ANSWERS = 3


def _marked_answers(s: Session, *, student_id: UUID, subject_id: UUID) -> list[events.EventView]:
    history = [
        ev for ev in events.list_events(s, student_id=student_id, types=EVENT_TYPES) if ev.subject_id == subject_id
    ]
    overridden = {
        events.EvaluationOverridden.model_validate(ev.payload).evaluation_id
        for ev in history
        if ev.type == "evaluation_overridden"
    }
    kept = []
    for ev in history:
        if ev.type != "attempt_evaluated":
            continue
        payload = events.AttemptEvaluated.model_validate(ev.payload)
        # A reviewed mark replaces the model's total, so the model's AO split no longer describes it.
        if payload.status == "final" and payload.evaluation_id not in overridden:
            kept.append(ev)
    return kept


def _items_for_attempts(s: Session, event_views: list[events.EventView]) -> dict[UUID, QuestionItem]:
    attempt_ids = [events.AttemptEvaluated.model_validate(ev.payload).attempt_id for ev in event_views]
    if not attempt_ids:
        return {}
    rows = s.execute(
        select(Attempt.id, QuestionItem)
        .join(QuestionItem, QuestionItem.id == Attempt.question_item_id)
        .where(Attempt.id.in_(attempt_ids))
    ).all()
    return {attempt_id: item for attempt_id, item in rows}


def _skill_names(s: Session, subject_id: UUID) -> dict[str, tuple[UUID, str]]:
    return curriculum.skills_by_code(s, subject_id)


def _splits(
    event_views: list[events.EventView], items: dict[UUID, QuestionItem], skill_by_id: dict[UUID, str]
) -> list[rules.MarkSplit]:
    found = []
    for ev in event_views:
        payload = events.AttemptEvaluated.model_validate(ev.payload)
        item = items.get(payload.attempt_id)
        if item is None:
            continue
        codes = tuple(skill_by_id[sid] for sid in (item.skill_ids or []) if sid in skill_by_id)
        if not codes:
            continue
        found.append(
            rules.MarkSplit(
                marks_available=payload.marks_available,
                per_skill=dict(payload.skill_marks or {}),
                skill_codes=codes,
            )
        )
    return found


def _topic_rows(s: Session, subject_id: UUID) -> list[Topic]:
    return list(
        s.scalars(select(Topic).where(Topic.subject_id == subject_id, Topic.depth == 0).order_by(Topic.position))
    )


def _topic_evidence(
    s: Session,
    *,
    student_id: UUID,
    subject_id: UUID,
    event_views: list[events.EventView],
    items: dict[UUID, QuestionItem],
) -> tuple[list[rules.TopicEvidence], dict[str, UUID]]:
    topics = _topic_rows(s, subject_id)
    objective_topic: dict[UUID, UUID] = {}
    counts: dict[UUID, int] = defaultdict(int)
    for objective_id, topic_id in s.execute(
        select(LearningObjective.id, Topic.id)
        .join(Topic, Topic.id == LearningObjective.topic_id)
        .where(Topic.subject_id == subject_id)
    ).all():
        objective_topic[objective_id] = topic_id
        counts[topic_id] += 1

    secure: dict[UUID, int] = defaultdict(int)
    for row in mastery.list_mastery(s, student_id=student_id, subject_id=subject_id):
        if row.level >= int(MasteryLevel.COMPETENT) and row.objective_id in objective_topic:
            secure[objective_topic[row.objective_id]] += 1

    awarded: dict[UUID, float] = defaultdict(float)
    available: dict[UUID, float] = defaultdict(float)
    answers: dict[UUID, int] = defaultdict(int)
    for ev in event_views:
        payload = events.AttemptEvaluated.model_validate(ev.payload)
        item = items.get(payload.attempt_id)
        if item is None:
            continue
        topic_ids = {objective_topic[oid] for oid in (item.objective_ids or []) if oid in objective_topic}
        for topic_id in topic_ids:
            awarded[topic_id] += payload.marks_awarded / len(topic_ids)
            available[topic_id] += payload.marks_available / len(topic_ids)
            answers[topic_id] += 1

    return [
        rules.TopicEvidence(
            topic_code=topic.code,
            topic_name=topic.name,
            marks_awarded=awarded[topic.id],
            marks_available=available[topic.id],
            answers=answers[topic.id],
            objectives_total=counts[topic.id],
            objectives_secure=secure[topic.id],
        )
        for topic in topics
    ], {t.code: t.id for t in topics}


def _command_words(
    s: Session,
    *,
    subject_id: UUID,
    event_views: list[events.EventView],
    items: dict[UUID, QuestionItem],
) -> list[CommandWordOut]:
    pool: dict[str, int] = defaultdict(int)
    for (command_word,) in s.execute(
        select(QuestionItem.command_word).where(
            QuestionItem.subject_id == subject_id, QuestionItem.verification_status == "verified"
        )
    ).all():
        if command_word:
            pool[command_word] += 1

    awarded: dict[str, float] = defaultdict(float)
    available: dict[str, float] = defaultdict(float)
    answers: dict[str, int] = defaultdict(int)
    for ev in event_views:
        payload = events.AttemptEvaluated.model_validate(ev.payload)
        item = items.get(payload.attempt_id)
        if item is None or not item.command_word:
            continue
        awarded[item.command_word] += payload.marks_awarded
        available[item.command_word] += payload.marks_available
        answers[item.command_word] += 1

    out = [
        CommandWordOut(
            command_word=word,
            share=round(awarded[word] / available[word], 4) if available[word] > 0 else None,
            answers=answers[word],
            marks_available=round(available[word], 2),
            items_available=count,
        )
        for word, count in pool.items()
    ]

    # Weakest first, but only where enough has been answered to mean anything; the rest trail by name.
    def order(row: CommandWordOut) -> tuple[int, float, str]:
        judged = row.answers >= MIN_COMMAND_WORD_ANSWERS and row.share is not None
        return (0 if judged else 1, row.share if judged and row.share is not None else 0.0, row.command_word)

    return sorted(out, key=order)


def _papers(s: Session, subject_id: UUID) -> dict[str, dict[str, object]]:
    """Whole past papers in the bank, keyed by "<syllabus>/<component>/<series>"."""
    found: dict[str, dict[str, object]] = {}
    for source_ref, marks in s.execute(
        select(QuestionItem.source_ref, QuestionItem.marks).where(
            QuestionItem.subject_id == subject_id,
            QuestionItem.verification_status == "verified",
            QuestionItem.origin == "past_paper",
            QuestionItem.source_ref.is_not(None),
        )
    ).all():
        parts = (source_ref or "").split("/")
        if len(parts) < 4:
            continue
        key = "/".join(parts[:3])
        entry = found.setdefault(key, {"questions": 0, "marks": 0})
        entry["questions"] = int(entry["questions"]) + 1
        entry["marks"] = int(entry["marks"]) + int(marks)
    return found


def _days_to_exam(exam_session: str | None, today: date) -> int | None:
    """Exam sessions are a month ("2027-06"); Cambridge sits IGCSE mid-month, so the 15th is the marker."""
    if not exam_session or len(exam_session) != 7:
        return None
    try:
        year, month = (int(part) for part in exam_session.split("-"))
        return (date(year, month, 15) - today).days
    except ValueError:
        return None


def readiness(s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID, today: date) -> ReadinessOut:
    require_student_access(principal, student_id, SCOPE)
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        raise not_found("subject")
    config = subjects.taught_config_for(subject.code)

    skills = _skill_names(s, subject_id)
    skill_by_id = {sid: code for code, (sid, _name) in skills.items()}
    event_views = _marked_answers(s, student_id=student_id, subject_id=subject_id)
    items = _items_for_attempts(s, event_views)

    skill_codes = sorted(skills)
    skill_rows = rules.skill_readiness(
        _splits(event_views, items, skill_by_id), skill_codes=skill_codes, weightings=config.skill_weights
    )
    topic_evidence, topic_ids = _topic_evidence(
        s, student_id=student_id, subject_id=subject_id, event_views=event_views, items=items
    )
    topic_rows = rules.topic_readiness(topic_evidence)
    command_words = _command_words(s, subject_id=subject_id, event_views=event_views, items=items)

    papers = _papers(s, subject_id)
    sat = {
        (row.config or {}).get("paper_ref")
        for row in s.scalars(
            select(Assessment).where(
                Assessment.student_id == student_id,
                Assessment.subject_id == subject_id,
                Assessment.kind == "exam_style",
                Assessment.status != "abandoned",  # an abandoned sitting is not a paper sat
            )
        )
        if (row.config or {}).get("paper_ref")
    }

    enrolled = next((e for e in enrollment.list_enrollments(s, [student_id]) if e.subject_id == subject_id), None)
    exam_session = enrolled.exam_session if enrolled else None

    notes: list[str] = []
    if not event_views:
        notes.append("No marked answers in this subject yet, so nothing here can be judged.")
    unjudged = [r.skill_code for r in skill_rows if r.band == "unknown"]
    if unjudged and event_views:
        notes.append(
            f"Not enough marked work yet to judge {', '.join(unjudged)} — "
            f"each needs about {int(rules.MIN_MARKS)} marks of answers split by objective."
        )
    if config.evaluation and not config.evaluation.calibrated:
        notes.append(
            "Every mark in this subject waits for your review before it counts, so readiness moves only "
            "after you have checked the work."
        )

    return ReadinessOut(
        subject_id=subject_id,
        subject_name=subject.name,
        exam_session=exam_session,
        days_to_exam=_days_to_exam(exam_session, today),
        rule_version=rules.RULE_VERSION,
        weighted_share=rules.weighted_share(skill_rows),
        notes=notes,
        skills=[SkillReadinessOut(**{**row.__dict__, "skill_name": skills[row.skill_code][1]}) for row in skill_rows],
        topics=[TopicReadinessOut(**{**row.__dict__, "topic_id": topic_ids[row.topic_code]}) for row in topic_rows],
        command_words=command_words,
        papers_available=len(papers),
        papers_sat=len(sat),
    )


def past_papers(s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID) -> list[PastPaperOut]:
    """Whole papers that can be sat under their own time limit (AC-R3)."""
    require_student_access(principal, student_id, SCOPE)
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        raise not_found("subject")

    durations: dict[str, int | None] = {}
    paper_marks: dict[str, int | None] = {}
    tree = curriculum.subject_tree(s, subject_id)
    if tree is not None:
        durations = {c.code: c.duration_min for c in tree.subject.components}
        paper_marks = {c.code: c.marks for c in tree.subject.components}

    config = subjects.config_for(subject.code)
    structures = config.paper_structure if isinstance(config, subjects.TaughtSubjectConfig) else {}
    sat: dict[str, tuple[date | None, UUID, bool]] = {}
    for row in s.scalars(
        select(Assessment).where(
            Assessment.student_id == student_id,
            Assessment.subject_id == subject_id,
            Assessment.kind == "exam_style",
            Assessment.status != "abandoned",  # an abandoned sitting is neither sat nor resumable
        )
    ):
        ref = (row.config or {}).get("paper_ref")
        if ref:
            sat[ref] = ((row.submitted_at.date() if row.submitted_at else None), row.id, row.status == "in_progress")

    out: list[PastPaperOut] = []
    for key, entry in sorted(_papers(s, subject_id).items()):
        _syllabus, component, series = key.split("/")[:3]
        component_code = f"P{component[0]}"
        seen = sat.get(key)
        structure = structures.get(component_code)
        out.append(
            PastPaperOut(
                paper_ref=key,
                component_code=component_code,
                label=f"Paper {component} · {series}",
                questions=int(entry["questions"]),
                bank_marks=int(entry["marks"]),
                paper_marks=paper_marks.get(component_code),
                duration_min=durations.get(component_code),
                sat_on=seen[0] if seen else None,
                assessment_id=seen[1] if seen else None,
                question_numbers=paper_questions(s, subject_id=subject_id, paper_ref=key),
                compulsory=list(structure.compulsory) if structure else [],
                choose_from=list(structure.choose_from) if structure else [],
                choose_count=structure.choose_count if structure else 0,
                in_progress=bool(seen and seen[2]),
            )
        )
    return out


QUESTION_REF = re.compile(r"/(Q\d+)")


def _paper_items(s: Session, *, subject_id: UUID, paper_ref: str) -> list[tuple[UUID, str, str]]:
    """(item id, source ref, question) for one past paper, in the paper's own order."""
    rows = s.execute(
        select(QuestionItem.id, QuestionItem.source_ref).where(
            QuestionItem.subject_id == subject_id,
            QuestionItem.verification_status == "verified",
            QuestionItem.origin == "past_paper",
            QuestionItem.source_ref.like(f"{paper_ref}/%"),
        )
    ).all()
    found = []
    for item_id, source_ref in rows:
        match = QUESTION_REF.search(source_ref or "")
        if match:
            found.append((item_id, source_ref or "", match.group(1)))
    return sorted(found, key=lambda r: curriculum.code_sort_key(r[1]))


def paper_questions(s: Session, *, subject_id: UUID, paper_ref: str) -> list[str]:
    """The question numbers a paper contains, in order — what the student chooses between."""
    found = {question for _id, _ref, question in _paper_items(s, subject_id=subject_id, paper_ref=paper_ref)}
    return sorted(found, key=lambda q: int(q[1:]) if q[1:].isdigit() else 0)  # Q2 before Q10


def sitting_items(
    s: Session, *, subject_id: UUID, paper_ref: str, component_code: str, chosen: Sequence[str]
) -> list[UUID]:
    """The items she will actually answer: the compulsory questions plus her choice, in paper order (AC-R3).

    The choice rule is the syllabus's, held in the subject config — a paper that offers three questions and
    expects two must not be served whole, or the mark total is meaningless.
    """
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        raise not_found("subject")
    structure = subjects.taught_config_for(subject.code).paper_structure.get(component_code)
    items = _paper_items(s, subject_id=subject_id, paper_ref=paper_ref)
    if not items:
        raise not_found("paper")
    if structure is None:
        return [item_id for item_id, _ref, _q in items]
    try:
        answering = set(structure.validate_choice(chosen))
    except ValueError as exc:
        raise ApiError(422, "invalid_question_choice", str(exc)) from None
    return [item_id for item_id, _ref, question in items if question in answering]


def sitting_assessment_id(s: Session, *, student_id: UUID, subject_id: UUID, paper_ref: str) -> UUID | None:
    for row in s.scalars(
        select(Assessment).where(
            Assessment.student_id == student_id,
            Assessment.subject_id == subject_id,
            Assessment.kind == "exam_style",
            Assessment.status != "abandoned",  # an abandoned sitting is neither sat nor resumable
        )
    ):
        if (row.config or {}).get("paper_ref") == paper_ref:
            return row.id
    return None


def time_used(row: Assessment, *, now: datetime) -> tuple[int | None, int | None, bool]:
    """(minutes allowed, minutes left, over time). A sitting is never cut off — losing her work would be
    worse than an overrun — but the overrun is recorded so the readiness view can say she ran out of time."""
    allowed = (row.config or {}).get("duration_min")
    if not allowed or row.started_at is None:
        return allowed, None, False
    used = (now - row.started_at).total_seconds() / 60
    end = row.submitted_at or now
    final_used = (end - row.started_at).total_seconds() / 60
    return int(allowed), max(0, int(allowed - used)), final_used > allowed


def start_sitting(
    s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID, body: SittingIn, now: datetime
) -> SittingOut:
    """Create (or resume) a timed sitting of one past paper and start its clock (AC-R3)."""
    require_student_access(principal, student_id, "assessments")
    papers = {p.paper_ref: p for p in past_papers(s, principal, student_id=student_id, subject_id=subject_id)}
    paper = papers.get(body.paper_ref)
    if paper is None:
        raise not_found("paper")

    existing = sitting_assessment_id(s, student_id=student_id, subject_id=subject_id, paper_ref=body.paper_ref)
    if existing is not None:
        row = s.get(Assessment, existing)
        if row is not None:
            return _sitting_out(s, row, paper.label, now=now)

    item_ids = sitting_items(
        s,
        subject_id=subject_id,
        paper_ref=body.paper_ref,
        component_code=paper.component_code or "",
        chosen=body.questions,
    )
    assessment_id = assessment.create_assessment(
        s,
        principal,
        AssessmentCreate(subject_id=subject_id, kind="exam_style", question_item_ids=item_ids),
        student_id=student_id,
        now=now,
    )
    row = s.get(Assessment, assessment_id)
    assert row is not None
    # The paper it came from and its real time limit, so the sitting can be recognised and timed later.
    row.config = {
        **(row.config or {}),
        "paper_ref": body.paper_ref,
        "duration_min": paper.duration_min,
        "questions": sorted(body.questions),
    }
    assessment.start_assessment(s, principal, assessment_id, now=now)
    s.flush()
    return _sitting_out(s, row, paper.label, now=now)


def _sitting_out(s: Session, row: Assessment, label: str, *, now: datetime) -> SittingOut:
    allowed, left, over = time_used(row, now=now)
    config = row.config or {}
    items = (
        s.execute(select(AssessmentItem.question_item_id).where(AssessmentItem.assessment_id == row.id)).scalars().all()
    )
    return SittingOut(
        assessment_id=row.id,
        paper_ref=str(config.get("paper_ref", "")),
        label=label,
        questions=list(config.get("questions") or []),
        items=len(items),
        marks=int(config.get("total_marks") or 0),
        duration_min=allowed,
        minutes_left=left,
        over_time=over,
        status=row.status,
    )


def sitting(s: Session, principal: Principal, *, student_id: UUID, assessment_id: UUID, now: datetime) -> SittingOut:
    require_student_access(principal, student_id, "assessments")
    row = s.get(Assessment, assessment_id)
    if row is None or row.student_id != student_id or row.kind != "exam_style":
        raise not_found("sitting")
    ref = str((row.config or {}).get("paper_ref", ""))
    label = ref.replace("/", " · ") if ref else "Past paper"
    return _sitting_out(s, row, label, now=now)
