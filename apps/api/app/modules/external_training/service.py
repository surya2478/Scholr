"""External training: record what happened in a class Scholr does not teach, and trace it back to IGCSE work.

The rule (docs/PHASE-3.md §1): complement, never duplicate. A log is evidence about a subject the student
learns elsewhere; the only thing Scholr does with it is reinforce the concepts underneath it in a subject it
does teach. Nothing here writes mastery (AC-X3) and nothing here can target an external objective (AC-X10).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.events import service as events
from app.modules.external_training import trace
from app.modules.external_training.models import ExternalTrainingLog
from app.modules.external_training.schemas import (
    ExternalSummaryOut,
    ExternalTrainingIn,
    ExternalTrainingOut,
    LessonRef,
    LessonStandingOut,
    ReinforcementOut,
    SubjectStandingOut,
)
from app.modules.mastery import service as mastery
from app.modules.mistakes import service as mistakes
from app.modules.subjects import service as subjects

SCOPE = "progress"
RECENT_LIMIT = 10
REINFORCEMENT_LIMIT = 6
# How far back a class still steers today's work. Beyond this the recency weight has decayed to nothing useful.
TRACE_WINDOW_DAYS = 60
# No score and no question count, but the session was flagged as difficult: treat it as "most of it did not land".
FLAGGED_SEVERITY = 0.6


class ExternalTrainingError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(400, code, message)


def _external_subject(s: Session, subject_id: UUID) -> curriculum.SubjectSummary:
    """The subject must exist and must be one the student learns elsewhere.

    Only `stage: external` qualifies. A `planned` subject is Scholr's own — it has a syllabus and simply no
    questions yet — so recording it here would file her school work as coaching-centre work.
    """
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        raise not_found("subject")
    try:
        config = subjects.config_for(subject.code)
    except subjects.SubjectConfigError:
        raise not_found("subject") from None
    if config.stage != "external":
        raise ExternalTrainingError(
            "subject_not_external",
            "this is one of Scholr's own subjects — record its work as practice, not outside training",
        )
    return subject


def _lesson_refs(s: Session, objective_ids: Sequence[UUID]) -> list[LessonRef]:
    summaries = curriculum.objective_summaries(s, list(objective_ids))
    ordered = [summaries[oid] for oid in objective_ids if oid in summaries]
    ordered.sort(key=lambda o: curriculum.code_sort_key(o.code))
    return [LessonRef(objective_id=o.id, code=o.code, title=o.statement) for o in ordered]


def _out(s: Session, row: ExternalTrainingLog, subject_name: str) -> ExternalTrainingOut:
    return ExternalTrainingOut(
        id=row.id,
        subject_id=row.subject_id,
        subject_name=subject_name,
        kind=row.kind,  # type: ignore[arg-type]
        title=row.title,
        occurred_on=row.occurred_on,
        duration_min=row.duration_min,
        lessons=_lesson_refs(s, row.objective_ids),
        weak_lessons=_lesson_refs(s, row.weak_objective_ids),
        score=float(row.score) if row.score is not None else None,
        max_score=float(row.max_score) if row.max_score is not None else None,
        questions_attempted=row.questions_attempted,
        questions_missed=row.questions_missed,
        weaknesses=list(row.weaknesses),
        notes=row.notes,
    )


def record(
    s: Session, principal: Principal, *, student_id: UUID, body: ExternalTrainingIn, now: datetime | None = None
) -> ExternalTrainingOut:
    require_student_access(principal, student_id, SCOPE)
    now = now or datetime.now(UTC)
    subject = _external_subject(s, body.subject_id)

    summaries = curriculum.objective_summaries(s, body.objective_ids)
    stray = [oid for oid in body.objective_ids if summaries.get(oid) is None or summaries[oid].subject_id != subject.id]
    if stray:
        raise ExternalTrainingError("objective_not_in_subject", "some lessons do not belong to that course")

    row = ExternalTrainingLog(
        tenant_id=principal.tenant_id,
        student_id=student_id,
        subject_id=subject.id,
        kind=body.kind,
        title=body.title,
        occurred_on=body.occurred_on,
        duration_min=body.duration_min,
        objective_ids=list(body.objective_ids),
        weak_objective_ids=list(body.weak_objective_ids),
        score=Decimal(str(body.score)) if body.score is not None else None,
        max_score=Decimal(str(body.max_score)) if body.max_score is not None else None,
        questions_attempted=body.questions_attempted,
        questions_missed=body.questions_missed,
        weaknesses=list(body.weaknesses),
        notes=body.notes,
        recorded_by_role=principal.role,
    )
    s.add(row)
    s.flush()

    # The event carries counts only — no note text, no weakness wording (events/schemas.py).
    events.append(
        s,
        tenant_id=principal.tenant_id,
        student_id=student_id,
        event_type="external_training_logged",
        payload={
            "external_training_log_id": row.id,
            "kind": row.kind,
            "duration_min": row.duration_min,
            "score": float(row.score) if row.score is not None else None,
            "max_score": float(row.max_score) if row.max_score is not None else None,
            "questions_attempted": row.questions_attempted,
            "questions_missed": row.questions_missed,
            "lessons": len(row.objective_ids),
            "weak_lessons": len(row.weak_objective_ids),
        },
        subject_id=subject.id,
        objective_ids=list(body.objective_ids),
        occurred_at=datetime.combine(body.occurred_on, datetime.min.time(), tzinfo=UTC),
        ref_type="external_training_log",
        ref_id=row.id,
    )
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="external_training.recorded",
        entity_type="external_training_log",
        entity_id=row.id,
        student_id=student_id,
    )
    return _out(s, row, subject.name)


def list_logs(
    s: Session, principal: Principal, *, student_id: UUID, limit: int = RECENT_LIMIT
) -> list[ExternalTrainingOut]:
    require_student_access(principal, student_id, SCOPE)
    rows = list(
        s.scalars(
            select(ExternalTrainingLog)
            .where(ExternalTrainingLog.student_id == student_id)
            .order_by(ExternalTrainingLog.occurred_on.desc(), ExternalTrainingLog.created_at.desc())
            .limit(limit)
        )
    )
    names = curriculum.subject_summaries(s, [r.subject_id for r in rows])
    return [_out(s, r, names[r.subject_id].name if r.subject_id in names else "") for r in rows]


# --- tracing -------------------------------------------------------------------------------------------------


def logs_for_lesson(s: Session, *, student_id: UUID, objective_id: UUID) -> list[tuple[ExternalTrainingOut, bool]]:
    """Every logged session that covered one external lesson, newest first, with whether she struggled on it."""
    rows = list(
        s.scalars(
            select(ExternalTrainingLog)
            .where(ExternalTrainingLog.student_id == student_id, ExternalTrainingLog.objective_ids.any(objective_id))
            .order_by(ExternalTrainingLog.occurred_on.desc(), ExternalTrainingLog.created_at.desc())
        )
    )
    names = curriculum.subject_summaries(s, [r.subject_id for r in rows])
    return [
        (
            _out(s, r, names[r.subject_id].name if r.subject_id in names else ""),
            objective_id in (r.weak_objective_ids or []),
        )
        for r in rows
    ]


def lesson_counts(s: Session, *, student_id: UUID, subject_id: UUID) -> dict[UUID, tuple[int, bool]]:
    """objective_id -> (sessions that covered it, whether any of them flagged it as hard), for one course."""
    counts: dict[UUID, tuple[int, bool]] = {}
    for covered, weak in s.execute(
        select(ExternalTrainingLog.objective_ids, ExternalTrainingLog.weak_objective_ids).where(
            ExternalTrainingLog.student_id == student_id, ExternalTrainingLog.subject_id == subject_id
        )
    ):
        for oid in covered or ():
            seen, hard = counts.get(oid, (0, False))
            counts[oid] = (seen + 1, hard or oid in (weak or ()))
    return counts


def severity_of(row: ExternalTrainingLog) -> float:
    """How badly it went, 0..1. Marks first, then the question count, then the fact it was flagged at all."""
    if row.score is not None and row.max_score is not None and row.max_score > 0:
        return max(0.0, min(1.0, 1.0 - float(row.score) / float(row.max_score)))
    if row.questions_attempted and row.questions_missed is not None:
        return max(0.0, min(1.0, row.questions_missed / row.questions_attempted))
    if row.weak_objective_ids or row.weaknesses:
        return FLAGGED_SEVERITY
    return 0.0


def weaknesses_from(rows: Sequence[ExternalTrainingLog]) -> list[trace.Weakness]:
    """One weakness per flagged lesson. A log with no flagged lesson but a poor score flags all it covered."""
    found: list[trace.Weakness] = []
    for row in rows:
        severity = severity_of(row)
        if severity <= 0:
            continue
        lessons = row.weak_objective_ids or row.objective_ids
        found.extend(
            trace.Weakness(objective_id=oid, occurred_on=row.occurred_on, severity=severity) for oid in lessons
        )
    return found


def _reinforceable_subjects(s: Session, student_id: UUID) -> dict[UUID, bool]:
    """Subjects a reinforcement target may live in -> whether Scholr can actually set work in one.

    Everything Scholr teaches, plus everything it has planned: a planned subject (Physics 0625, Chemistry
    0620 today) has a syllabus but no question bank or marking, so it can only be named as something to
    revise from the course book. Subjects the student learns elsewhere are never targets (AC-X10).
    """
    found: dict[UUID, bool] = {}
    enrolled = {e.subject_id for e in enrollment.list_enrollments(s, [student_id])}
    for subject in curriculum.list_subject_summaries(s):
        try:
            config = subjects.config_for(subject.code)
        except subjects.SubjectConfigError:
            continue
        if not config.can_suggest_revision:
            continue
        # A taught subject must be one she is actually enrolled in; a planned one is not enrolled yet.
        if config.taught_here and subject.id not in enrolled:
            continue
        found[subject.id] = config.taught_here
    return found


def _graph(s: Session, weaknesses: Sequence[trace.Weakness], taught_subject_ids: Sequence[UUID]) -> trace.ConceptGraph:
    lesson_ids = [w.objective_id for w in weaknesses]
    concepts_of_objective = curriculum.concepts_of_objectives(s, lesson_ids)

    reached: set[UUID] = {cid for ids in concepts_of_objective.values() for cid in ids}
    frontier = set(reached)
    prerequisites: dict[UUID, tuple[tuple[UUID, float], ...]] = {}
    for _ in range(trace.MAX_DEPTH):
        hop = curriculum.prerequisites_of_concepts(s, list(frontier))
        prerequisites.update(hop)
        frontier = {pid for pairs in hop.values() for pid, _ in pairs} - reached
        reached |= frontier
        if not frontier:
            break

    return trace.ConceptGraph(
        concepts_of_objective=concepts_of_objective,
        prerequisites=prerequisites,
        objectives_of_concept=curriculum.objectives_of_concepts(s, list(reached), subject_ids=taught_subject_ids),
        concept_names={cid: view.name for cid, view in curriculum.concept_views(s, list(reached)).items()},
    )


def _standings(s: Session, student_id: UUID, objective_ids: Sequence[UUID]) -> dict[UUID, trace.Standing]:
    wanted = set(objective_ids)
    levels = {m.objective_id: m for m in mastery.list_mastery(s, student_id=student_id) if m.objective_id in wanted}
    open_counts: dict[UUID, int] = defaultdict(int)
    for pattern in mistakes.list_mistakes(s, student_id=student_id):
        if pattern.objective_id in wanted and pattern.status != "resolved":
            open_counts[pattern.objective_id] += 1
    return {
        objective_id: trace.Standing(
            level=levels[objective_id].level if objective_id in levels else None,
            open_mistakes=open_counts.get(objective_id, 0),
            retention_risk=levels[objective_id].retention_risk if objective_id in levels else "none",
        )
        for objective_id in wanted
    }


def minutes_on(s: Session, *, student_id: UUID, day: date) -> int:
    """Minutes of external classes and homework she recorded for ``day`` (sessions with no duration add nothing)."""
    total = s.scalar(
        select(func.coalesce(func.sum(ExternalTrainingLog.duration_min), 0)).where(
            ExternalTrainingLog.student_id == student_id, ExternalTrainingLog.occurred_on == day
        )
    )
    return int(total or 0)


def _recent_rows(s: Session, student_id: UUID, today: date) -> list[ExternalTrainingLog]:
    cutoff = today.toordinal() - TRACE_WINDOW_DAYS
    return list(
        s.scalars(
            select(ExternalTrainingLog)
            .where(
                ExternalTrainingLog.student_id == student_id,
                ExternalTrainingLog.occurred_on >= date.fromordinal(max(1, cutoff)),
            )
            .order_by(ExternalTrainingLog.occurred_on.desc())
        )
    )


def reinforcement(
    s: Session,
    *,
    student_id: UUID,
    today: date,
    limit: int = REINFORCEMENT_LIMIT,
    practicable_only: bool = False,
) -> list[ReinforcementOut]:
    """Ranked IGCSE objectives to reinforce because of recent external classes. No LLM, no writes.

    ``practicable_only`` narrows the *subjects searched*, not the finished list. The planner needs the best
    target it can actually set work on: filtering afterwards would hand it an empty day whenever the top few
    happen to be in a subject Scholr has only planned.
    """
    return _targets_for(
        s,
        student_id=student_id,
        weaknesses=weaknesses_from(_recent_rows(s, student_id, today)),
        today=today,
        limit=limit,
        practicable_only=practicable_only,
    )


def ground_under(s: Session, *, student_id: UUID, objective_id: UUID, today: date) -> list[ReinforcementOut]:
    """The IGCSE objectives an external lesson rests on and she is not yet secure in, whether or not a class on
    it has been logged — the IIT lesson page's "ground underneath" (docs/STUDENT-APP.md step 5). No writes."""
    return _targets_for(
        s,
        student_id=student_id,
        weaknesses=[trace.Weakness(objective_id=objective_id, occurred_on=today, severity=1.0)],
        today=today,
        limit=REINFORCEMENT_LIMIT,
        practicable_only=False,
    )


def _targets_for(
    s: Session,
    *,
    student_id: UUID,
    weaknesses: Sequence[trace.Weakness],
    today: date,
    limit: int,
    practicable_only: bool,
) -> list[ReinforcementOut]:
    if not weaknesses:
        return []
    reinforceable = _reinforceable_subjects(s, student_id)
    if practicable_only:
        reinforceable = {sid: ok for sid, ok in reinforceable.items() if ok}
    if not reinforceable:
        return []
    graph = _graph(s, weaknesses, list(reinforceable))
    candidates = {oid for ids in graph.objectives_of_concept.values() for oid in ids}
    found = trace.targets(weaknesses, graph, _standings(s, student_id, list(candidates)), today=today, limit=limit)

    objectives = curriculum.objective_summaries(s, [t.objective_id for t in found])
    lessons = curriculum.objective_summaries(s, [t.from_objective_id for t in found])
    subject_names = curriculum.subject_summaries(s, [o.subject_id for o in objectives.values()])
    notes = curriculum.concept_views(s, [t.concept_id for t in found])

    out: list[ReinforcementOut] = []
    for target in found:
        objective = objectives.get(target.objective_id)
        lesson = lessons.get(target.from_objective_id)
        if objective is None or lesson is None:
            continue
        out.append(
            ReinforcementOut(
                objective_id=objective.id,
                objective_code=objective.code,
                objective_statement=objective.statement,
                subject_id=objective.subject_id,
                subject_name=subject_names[objective.subject_id].name,
                concept=target.concept_name,
                depth=target.depth,
                practicable=reinforceable.get(objective.subject_id, False),
                reason=reason_for(target, lesson.statement),
                note=notes[target.concept_id].note if target.concept_id in notes else None,
                priority=target.priority,
            )
        )
    return out


def reason_for(target: trace.Target, lesson_title: str) -> str:
    """One sentence naming the class topic, so she knows why this appeared (AC-X12).

    At depth 0 the concept name is usually the lesson's own name, so saying both reads as a stutter.
    """
    if target.depth == 0:
        return f'This is the IGCSE side of your class on "{lesson_title}".'
    concept = target.concept_name.lower() if target.concept_name else "something underneath it"
    return f'Your class on "{lesson_title}" rests on {concept} — worth shoring that up first.'


# --- standing ------------------------------------------------------------------------------------------------


def _traceable(s: Session, subject_id: UUID) -> bool:
    """Whether this course's lessons reach the concept map at all.

    Physics, Chemistry and Biology are logged but cannot be traced until Scholr teaches their IGCSE
    counterparts (docs/PHASE-3.md §2). Saying so beats showing an empty suggestion list.
    """
    objective_ids = [oid for oid, _ in curriculum.objectives_by_code(s, subject_id).values()]
    return bool(curriculum.concepts_of_objectives(s, objective_ids))


def _subject_standing(
    s: Session, rows: Sequence[ExternalTrainingLog], subject: curriculum.SubjectSummary
) -> SubjectStandingOut:
    scored = [r for r in rows if r.score is not None and r.max_score is not None]
    awarded = sum(float(r.score) for r in scored if r.score is not None)
    available = sum(float(r.max_score) for r in scored if r.max_score is not None)
    covered = {oid for r in rows for oid in r.objective_ids}
    weak_counts: dict[UUID, list[ExternalTrainingLog]] = defaultdict(list)
    for row in rows:
        for objective_id in row.weak_objective_ids:
            weak_counts[objective_id].append(row)

    lesson_titles = curriculum.objective_summaries(s, list(weak_counts))
    weak_lessons: list[LessonStandingOut] = []
    for objective_id, logs in weak_counts.items():
        summary = lesson_titles.get(objective_id)
        if summary is None:
            continue
        lesson_scored = [r for r in logs if r.score is not None and r.max_score is not None]
        lesson_awarded = sum(float(r.score) for r in lesson_scored if r.score is not None)
        lesson_available = sum(float(r.max_score) for r in lesson_scored if r.max_score is not None)
        weak_lessons.append(
            LessonStandingOut(
                objective_id=objective_id,
                code=summary.code,
                title=summary.statement,
                sessions=len(logs),
                last_seen_on=max(r.occurred_on for r in logs),
                accuracy=round(lesson_awarded / lesson_available, 4) if lesson_available else None,
                flagged=True,
            )
        )
    weak_lessons.sort(key=lambda lesson: (-lesson.sessions, lesson.last_seen_on), reverse=False)

    return SubjectStandingOut(
        subject_id=subject.id,
        subject_name=subject.name,
        sessions=len(rows),
        minutes=sum(r.duration_min or 0 for r in rows),
        last_seen_on=max((r.occurred_on for r in rows), default=None),
        accuracy=round(awarded / available, 4) if available else None,
        lessons_covered=len(covered),
        lessons_total=curriculum.objective_counts(s, [subject.id]).get(subject.id, 0),
        traceable=_traceable(s, subject.id),
        weak_lessons=weak_lessons,
    )


def summary(s: Session, principal: Principal, *, student_id: UUID, today: date, weeks: int = 12) -> ExternalSummaryOut:
    require_student_access(principal, student_id, SCOPE)
    since = date.fromordinal(max(1, today.toordinal() - weeks * 7))
    rows = list(
        s.scalars(
            select(ExternalTrainingLog)
            .where(ExternalTrainingLog.student_id == student_id, ExternalTrainingLog.occurred_on >= since)
            .order_by(ExternalTrainingLog.occurred_on.desc())
        )
    )
    by_subject: dict[UUID, list[ExternalTrainingLog]] = defaultdict(list)
    for row in rows:
        by_subject[row.subject_id].append(row)
    subject_names = curriculum.subject_summaries(s, list(by_subject))

    standings = [
        _subject_standing(s, subject_rows, subject_names[subject_id])
        for subject_id, subject_rows in by_subject.items()
        if subject_id in subject_names
    ]
    standings.sort(key=lambda st: st.subject_name)
    recent = [
        _out(s, r, subject_names[r.subject_id].name) for r in rows[:RECENT_LIMIT] if r.subject_id in subject_names
    ]
    return ExternalSummaryOut(
        subjects=standings,
        recent=recent,
        reinforcement=reinforcement(s, student_id=student_id, today=today),
    )
