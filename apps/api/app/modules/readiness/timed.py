"""This week's timed question (improvement 4 of the IGCSE review).

Writing a long answer against the clock is its own exam skill, separate from knowing the content. Once a week she
writes one real, level-marked past-paper answer under exam conditions, timed at her own papers' pace — the
minutes her syllabus's papers allow divided by their marks — so twenty minutes for a 14-mark Sociology question.

Deterministic throughout, and nothing is stored beyond the timed sitting itself: the question is chosen by rule,
the time comes from the exam components, and the sitting is an ordinary `exam_style` assessment marked by the
subject's own pipeline (a provisional mark is shown to her without a number, AC-E6). A sitting is never cut off;
an overrun is recorded, as for a whole paper.

Which subjects: those whose config marks long answers in levels (`evaluation.pipeline: essay_levels`). The engine
never names a subject.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.assessment import service as assessment
from app.modules.assessment.models import Assessment, AssessmentItem, Attempt, QuestionItem
from app.modules.assessment.schemas import AssessmentCreate
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.identity import service as identity
from app.modules.learn import labels
from app.modules.mastery import service as mastery
from app.modules.readiness.schemas import TimedItemOut, TimedQuestionOut
from app.modules.studies import service as studies
from app.modules.subjects import service as subjects
from app.tools.dates import local_date

LONG_ANSWER_MARKS = 8  # the level-marked items (evaluation/essay_levels.LEVELS_FROM_MARKS)
CONFIG_KEY = "weekly_timed"
SCOPE = "assessments"


def week_start(day: date) -> date:
    """Weeks run Monday to Sunday."""
    return day - timedelta(days=day.weekday())


def minutes_for(marks: int, seconds_per_mark: float) -> int:
    return max(1, math.ceil(marks * seconds_per_mark / 60))


def eligible(subject_code: str) -> bool:
    try:
        config = subjects.taught_config_for(subject_code)
    except subjects.SubjectConfigError:
        return False
    return config.taught_here and config.evaluation.pipeline == "essay_levels"


def choose(
    candidates: Sequence[QuestionItem], *, met: set[UUID], answered: set[UUID], held_back: set[UUID]
) -> QuestionItem | None:
    """This week's question: never one she has answered, never on a topic the validation study holds back.
    A topic she has already met comes first (it tests writing to time, not unseen content); then the newest exam
    series (shaped like the papers she will sit); then the larger tariff, then the bank's own order, so the choice is
    the same every time it is asked for."""
    pool = [
        q for q in candidates if q.id not in answered and q.objective_ids and not (set(q.objective_ids) & held_back)
    ]

    def order(q: QuestionItem) -> tuple:
        year, month = labels.series_recency(q.source_ref)
        return (not (set(q.objective_ids) & met), -year, -month, -q.marks, q.source_ref or "", str(q.id))

    pool.sort(key=order)
    return pool[0] if pool else None


def _this_weeks_sitting(s: Session, *, student_id: UUID, subject_id: UUID, week: date) -> Assessment | None:
    rows = s.scalars(
        select(Assessment)
        .where(
            Assessment.student_id == student_id,
            Assessment.subject_id == subject_id,
            Assessment.kind == "exam_style",
        )
        .order_by(Assessment.created_at.desc())
    )
    return next((r for r in rows if (r.config or {}).get(CONFIG_KEY) == week.isoformat()), None)


def _candidates(s: Session, subject_id: UUID) -> list[QuestionItem]:
    return list(
        s.scalars(
            select(QuestionItem).where(
                QuestionItem.subject_id == subject_id,
                QuestionItem.verification_status == "verified",
                QuestionItem.reserved_for_study.is_(False),
                QuestionItem.marks >= LONG_ANSWER_MARKS,
            )
        )
    )


def _answered(s: Session, student_id: UUID, item_ids: Sequence[UUID]) -> set[UUID]:
    if not item_ids:
        return set()
    return set(
        s.scalars(
            select(Attempt.question_item_id).where(
                Attempt.student_id == student_id, Attempt.question_item_id.in_(list(item_ids))
            )
        )
    )


def _item_out(s: Session, item: QuestionItem, minutes: int) -> TimedItemOut:
    objective = curriculum.objective_summaries(s, list(item.objective_ids[:1])).get(item.objective_ids[0])
    return TimedItemOut(
        question_item_id=item.id,
        label=labels.item_label(item.source_ref, item.origin),
        marks=item.marks,
        command_word=item.command_word,
        objective_code=objective.code if objective else None,
        objective_statement=objective.statement if objective else None,
        minutes=minutes,
    )


def _status(row: Assessment | None, *, now: datetime) -> tuple[str, int | None, bool]:
    if row is None:
        return "to_do", None, False
    allowed = int((row.config or {}).get("duration_min") or 0)
    if row.started_at is None:
        return "to_do", None, False
    end = row.submitted_at or now
    used = math.ceil((end - row.started_at).total_seconds() / 60)
    status = {"in_progress": "in_progress", "submitted": "submitted", "evaluated": "marked"}.get(row.status, "to_do")
    return status, used, bool(allowed) and used > allowed


def _out(
    s: Session, *, student_id: UUID, subject_id: UUID, subject_name: str, week: date, now: datetime
) -> TimedQuestionOut | None:
    pace = curriculum.exam_seconds_per_mark(s, [subject_id]).get(subject_id)
    if pace is None:
        return None  # no timed component: no honest time limit to set
    row = _this_weeks_sitting(s, student_id=student_id, subject_id=subject_id, week=week)
    if row is not None:
        item_id = s.scalar(select(AssessmentItem.question_item_id).where(AssessmentItem.assessment_id == row.id))
        item = s.get(QuestionItem, item_id) if item_id else None
    else:
        candidates = _candidates(s, subject_id)
        met = {
            m.objective_id
            for m in mastery.list_mastery(s, student_id=student_id, subject_id=subject_id)
            if m.level >= 1
        }
        item = choose(
            candidates,
            met=met,
            answered=_answered(s, student_id, [c.id for c in candidates]),
            held_back=studies.control_objective_ids(s, student_id=student_id, at=now),
        )
    if item is None:
        return None
    minutes = int((row.config or {}).get("duration_min")) if row is not None else minutes_for(item.marks, pace)
    status, used, over = _status(row, now=now)
    return TimedQuestionOut(
        subject_id=subject_id,
        subject_name=subject_name,
        week_start=week,
        item=_item_out(s, item, minutes),
        assessment_id=row.id if row is not None else None,
        status=status,  # type: ignore[arg-type]
        minutes_used=used,
        over_time=over,
    )


def this_week(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> list[TimedQuestionOut]:
    """This week's timed question in each subject that has one."""
    require_student_access(principal, student_id, SCOPE)
    week = week_start(local_date(now, identity.student_timezone(s, student_id)))
    enrolled = [e.subject_id for e in enrollment.list_enrollments(s, [student_id])]
    found = []
    for subject_id, summary in sorted(curriculum.subject_summaries(s, enrolled).items(), key=lambda x: x[1].name):
        if not eligible(summary.code):
            continue
        out = _out(s, student_id=student_id, subject_id=subject_id, subject_name=summary.name, week=week, now=now)
        if out is not None:
            found.append(out)
    return found


def start(s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID, now: datetime) -> TimedQuestionOut:
    """Start this week's timed question (or return the one already started): its clock starts now."""
    require_student_access(principal, student_id, SCOPE)
    summary = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    enrolled = {e.subject_id for e in enrollment.list_enrollments(s, [student_id])}
    if summary is None or subject_id not in enrolled or not eligible(summary.code):
        raise not_found("timed question")
    week = week_start(local_date(now, identity.student_timezone(s, student_id)))
    current = _out(s, student_id=student_id, subject_id=subject_id, subject_name=summary.name, week=week, now=now)
    if current is None:
        raise ApiError(404, "no_timed_question", "There is no long-answer question left to set this week.")
    if current.assessment_id is not None:
        return current
    assessment_id = assessment.create_assessment(
        s,
        principal,
        AssessmentCreate(subject_id=subject_id, kind="exam_style", question_item_ids=[current.item.question_item_id]),
        student_id=student_id,
        now=now,
    )
    row = s.get(Assessment, assessment_id)
    assert row is not None
    row.config = {
        **(row.config or {}),
        CONFIG_KEY: week.isoformat(),
        "duration_min": current.item.minutes,
        "title": f"Timed question · {summary.name}",
    }
    assessment.start_assessment(s, principal, assessment_id, now=now)
    s.flush()
    out = _out(s, student_id=student_id, subject_id=subject_id, subject_name=summary.name, week=week, now=now)
    assert out is not None
    return out
