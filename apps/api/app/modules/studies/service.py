"""Validation study (PHASE-1 §5): arm assignments consumed by planning and practice selection, crossover, results."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.rbac import Principal, require_role, require_student_access
from app.modules.assessment import service as assessment
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.evaluation import service as evaluation
from app.modules.events import service as events
from app.modules.studies import results
from app.modules.studies.models import StudyAssignment
from app.modules.studies.schemas import (
    ArmResultOut,
    AssignmentOut,
    FormOut,
    PairCreate,
    StudyResultsOut,
    TopicScoreOut,
)

SCOPE = "assessments"
MARKED_STATUSES = ("final", "overridden")


def control_objective_ids(s: Session, *, student_id: UUID, at: datetime) -> set[UUID]:
    """Objectives in the control arm before their crossover (AC-P2: never planned or practised in the app)."""
    rows = s.scalars(
        select(StudyAssignment.objective_ids).where(
            StudyAssignment.student_id == student_id,
            StudyAssignment.arm == "control",
            or_(StudyAssignment.crossover_at.is_(None), StudyAssignment.crossover_at > at),
        )
    )
    return {objective_id for ids in rows for objective_id in ids}


def _require_study_manager(principal: Principal, student_id: UUID) -> None:
    require_role(principal, "guardian", "admin")  # the student is not shown arm labels or results mid-study
    require_student_access(principal, student_id, SCOPE)


def _assignments(s: Session, student_id: UUID, subject_id: UUID | None = None) -> list[StudyAssignment]:
    query = select(StudyAssignment).where(StudyAssignment.student_id == student_id)
    if subject_id is not None:
        query = query.where(StudyAssignment.subject_id == subject_id)
    return list(s.scalars(query.order_by(StudyAssignment.pair_code, StudyAssignment.arm)))


def _codes(s: Session, objective_ids: list[UUID]) -> dict[UUID, str]:
    return {oid: o.code for oid, o in curriculum.objective_summaries(s, objective_ids).items()}


def list_assignments(
    s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID | None = None
) -> list[AssignmentOut]:
    _require_study_manager(principal, student_id)
    rows = _assignments(s, student_id, subject_id)
    codes = _codes(s, [oid for r in rows for oid in r.objective_ids])
    return [
        AssignmentOut(
            id=r.id,
            subject_id=r.subject_id,
            pair_code=r.pair_code,
            arm=r.arm,
            objective_ids=list(r.objective_ids),
            objective_codes=[codes.get(oid, "?") for oid in r.objective_ids],
            assignment_method=r.assignment_method,
            assigned_at=r.assigned_at,
            crossover_at=r.crossover_at,
        )
        for r in rows
    ]


def create_pair(
    s: Session, principal: Principal, body: PairCreate, *, student_id: UUID, now: datetime
) -> list[AssignmentOut]:
    _require_study_manager(principal, student_id)
    app_ids, control_ids = set(body.app_objective_ids), set(body.control_objective_ids)
    if app_ids & control_ids:
        raise ApiError(422, "arms_overlap", "an objective cannot be in both arms")
    wanted = app_ids | control_ids
    found = curriculum.objective_summaries(s, list(wanted))
    if set(found) != wanted or any(o.subject_id != body.subject_id for o in found.values()):
        raise ApiError(422, "invalid_objectives", "every objective must exist and belong to the subject")
    existing = _assignments(s, student_id, body.subject_id)
    if any(r.pair_code == body.pair_code for r in existing):
        raise ApiError(409, "duplicate_pair", "this pair code is already used for the subject")
    if wanted & {oid for r in existing for oid in r.objective_ids}:
        raise ApiError(409, "objective_already_assigned", "an objective is already part of another pair")

    assigned_at = body.assigned_at or now
    for arm, ids in (("app", body.app_objective_ids), ("control", body.control_objective_ids)):
        s.add(
            StudyAssignment(
                tenant_id=principal.tenant_id,
                student_id=student_id,
                subject_id=body.subject_id,
                pair_code=body.pair_code,
                arm=arm,
                objective_ids=list(dict.fromkeys(ids)),
                assignment_method=body.assignment_method,
                assigned_at=assigned_at,
            )
        )
    s.flush()
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="study.assignment_created",
        entity_type="student",
        entity_id=student_id,
        student_id=student_id,
        meta={"subject_id": str(body.subject_id), "pair_code": body.pair_code},
    )
    return list_assignments(s, principal, student_id=student_id, subject_id=body.subject_id)


def crossover(
    s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID, now: datetime
) -> list[AssignmentOut]:
    """After the retention test, control topics get app support (PHASE-1 §5)."""
    _require_study_manager(principal, student_id)
    kinds = {sitting.kind for sitting in assessment.study_sittings(s, student_id=student_id, subject_id=subject_id)}
    if "retention" not in kinds:
        raise ApiError(409, "retention_not_done", "cross over only after the retention test is submitted")
    changed = 0
    for row in _assignments(s, student_id, subject_id):
        if row.crossover_at is None:
            row.crossover_at = now
            changed += 1
    s.flush()
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="study.crossover",
        entity_type="student",
        entity_id=student_id,
        student_id=student_id,
        meta={"subject_id": str(subject_id), "assignments": changed},
    )
    return list_assignments(s, principal, student_id=student_id, subject_id=subject_id)


def _score_out(score: results.TopicScore | None) -> TopicScoreOut | None:
    if score is None:
        return None
    return TopicScoreOut(
        awarded=score.awarded, available=score.available, ratio=score.ratio, provisional=score.provisional
    )


def study_results(
    s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID, now: datetime
) -> StudyResultsOut:
    _require_study_manager(principal, student_id)
    rows = _assignments(s, student_id, subject_id)
    raw = assessment.study_sittings(s, student_id=student_id, subject_id=subject_id)
    marks = evaluation.marks_for_attempts(s, [i.attempt_id for sit in raw for i in sit.items if i.attempt_id])

    def awarded(item: assessment.SittingItem) -> float | None:
        if item.attempt_id is None:
            return 0.0  # unanswered
        mark = marks.get(item.attempt_id)
        return mark.marks_awarded if mark is not None and mark.status in MARKED_STATUSES else None

    sittings = [
        results.FormSitting(
            kind=sit.kind,
            form_code=sit.form_code,
            submitted_at=sit.submitted_at,
            items=tuple(results.MarkedItem(frozenset(i.objective_ids), i.marks, awarded(i)) for i in sit.items),
        )
        for sit in raw
    ]
    arms = results.arm_results(
        [results.Assignment(r.pair_code, r.arm, frozenset(r.objective_ids)) for r in rows], sittings
    )
    latest = results.latest_sittings(sittings)
    start = latest["baseline"].submitted_at if "baseline" in latest else None
    end = latest["post"].submitted_at if "post" in latest else now
    session_events = (
        [
            ev
            for ev in events.list_events(
                s, student_id=student_id, types=("session_started", "session_ended"), since=start
            )
            if ev.subject_id == subject_id
        ]
        if start is not None
        else []
    )
    per_week, hours = results.engagement(
        [ev.occurred_at for ev in session_events if ev.type == "session_started"],
        [
            (ev.occurred_at, int(ev.payload.get("active_minutes", 0)))
            for ev in session_events
            if ev.type == "session_ended"
        ],
        start=start,
        end=end,
    )
    decision = results.decide(arms, sessions_per_week=per_week, app_hours=hours)
    codes = _codes(s, [oid for r in rows for oid in r.objective_ids])
    objectives_by_arm = {(r.pair_code, r.arm): sorted(codes.get(o, "?") for o in r.objective_ids) for r in rows}
    latest_ids = {sit.submitted_at: sit.assessment_id for sit in raw}
    return StudyResultsOut(
        student_id=student_id,
        subject_id=subject_id,
        generated_at=now,
        rule_version=decision.rule_version,
        forms=[
            FormOut(
                assessment_id=latest_ids[f.submitted_at],
                kind=f.kind,
                form_code=f.form_code,
                submitted_at=f.submitted_at,
            )
            for f in sorted(latest.values(), key=lambda f: f.submitted_at)
        ],
        arms=[
            ArmResultOut(
                pair_code=a.pair_code,
                arm=a.arm,
                objective_codes=objectives_by_arm.get((a.pair_code, a.arm), []),
                baseline=_score_out(a.baseline),
                post=_score_out(a.post),
                retention=_score_out(a.retention),
                gain=a.gain,
                retention_ratio=a.retention_ratio,
                eligible=a.eligible,
                overlapping_items=a.overlapping_items,
            )
            for a in arms
        ],
        decision=decision.decision,
        reasons=decision.reasons,
        provisional=decision.provisional,
        sessions_per_week=decision.sessions_per_week,
        app_hours=decision.app_hours,
        mean_gain_app=decision.mean_gain_app,
        mean_gain_control=decision.mean_gain_control,
        gain_difference=decision.gain_difference,
        mean_retention_app=decision.mean_retention_app,
        mean_retention_control=decision.mean_retention_control,
        learning_per_hour=decision.learning_per_hour,
    )
