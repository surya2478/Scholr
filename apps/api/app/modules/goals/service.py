"""Goals: set with the student, measured from evidence (Phase 2, AC-G1). No LLM.

Every reading comes from a module that already holds the evidence — mastery, mistakes, events — so a goal
cannot be marked achieved by anyone claiming it was. A goal a parent proposes waits for the student to agree
before it becomes active, which is what "set with the student" has to mean if it means anything.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, forbidden, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.events import service as events
from app.modules.goals import rules
from app.modules.goals.schemas import GoalIn, GoalOut
from app.modules.identity import service as identity
from app.modules.mastery import service as mastery
from app.modules.mastery.rules import MasteryLevel
from app.modules.mistakes import service as mistakes
from app.modules.planner.models import Goal
from app.tools.dates import local_date

SCOPE = "progress"
# The window the rate-style measures are averaged over, so a good week does not read as a solved goal.
WINDOW_DAYS = 28
HELPED_FROM_LEVEL = 2


def _reading(s: Session, *, student_id: UUID, measure: str, subject_id: UUID | None, today: date) -> float:
    """What the measure stands at right now, from the module that owns that evidence."""
    if measure == "topics_secure":
        rows = mastery.list_mastery(s, student_id=student_id, subject_id=subject_id)
        return float(sum(1 for r in rows if r.level >= int(MasteryLevel.COMPETENT)))

    if measure == "open_mistakes":
        rows = mistakes.list_mistakes(s, student_id=student_id, subject_id=subject_id)
        return float(sum(1 for r in rows if r.status != "resolved"))

    since = today - timedelta(days=WINDOW_DAYS - 1)
    timezone = identity.student_timezone(s, student_id)

    if measure == "active_days_per_week":
        days: set[date] = set()
        for ev in events.list_events(s, student_id=student_id, types=("session_ended",)):
            day = local_date(ev.occurred_at, timezone)
            if since <= day <= today and int(ev.payload.get("active_minutes") or 0) > 0:
                days.add(day)
        return round(len(days) / (WINDOW_DAYS / 7), 4)

    if measure == "answers_without_help":
        answered = unaided = 0
        for ev in events.list_events(s, student_id=student_id, types=("attempt_evaluated",)):
            day = local_date(ev.occurred_at, timezone)
            if not (since <= day <= today):
                continue
            payload = events.AttemptEvaluated.model_validate(ev.payload)
            if payload.status != "final":
                continue
            if subject_id is not None and ev.subject_id != subject_id:
                continue
            answered += 1
            unaided += payload.help_level < HELPED_FROM_LEVEL
        return round(100 * unaided / answered, 2) if answered else 0.0

    raise ApiError(422, "unknown_measure", f"cannot measure '{measure}'")


def _out(s: Session, row: Goal, *, today: date, subject_names: dict[UUID, str]) -> GoalOut:
    config = rules.measure_config(row.measure)
    current = _reading(s, student_id=row.student_id, measure=row.measure, subject_id=row.subject_id, today=today)
    progress = rules.progress(
        measure=row.measure,  # type: ignore[arg-type]
        current=current,
        target=row.target_value,
        baseline=row.baseline_value,
        target_date=row.target_date,
        today=today,
    )
    return GoalOut(
        id=row.id,
        statement=row.statement,
        measure=row.measure,
        measure_label=str(config["label"]),
        unit=str(config["unit"]),
        help=str(config["help"]),
        subject_id=row.subject_id,
        subject_name=subject_names.get(row.subject_id) if row.subject_id else None,
        status=row.status,
        proposed_by_role=row.proposed_by_role,
        agreed=row.agreed_at is not None,
        target_date=row.target_date,
        current=progress.current,
        target=progress.target,
        baseline=row.baseline_value,
        direction=progress.direction,
        share=progress.share,
        reached=progress.reached,
        days_left=progress.days_left,
        rule_version=row.rule_version,
    )


def list_goals(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> list[GoalOut]:
    require_student_access(principal, student_id, SCOPE)
    today = local_date(now, identity.student_timezone(s, student_id))
    rows = list(s.scalars(select(Goal).where(Goal.student_id == student_id).order_by(Goal.created_at.desc())))
    names = curriculum.subject_summaries(s, [r.subject_id for r in rows if r.subject_id])
    subject_names = {sid: summary.name for sid, summary in names.items()}
    return [_out(s, row, today=today, subject_names=subject_names) for row in rows]


def create_goal(s: Session, principal: Principal, *, student_id: UUID, body: GoalIn, now: datetime) -> GoalOut:
    require_student_access(principal, student_id, SCOPE)
    config = rules.measure_config(body.measure)
    if config["needs_subject"] and body.subject_id is None:
        raise ApiError(422, "subject_required", f"a {config['label']} goal has to name a subject")

    today = local_date(now, identity.student_timezone(s, student_id))
    current = _reading(s, student_id=student_id, measure=body.measure, subject_id=body.subject_id, today=today)
    if not rules.is_realistic(measure=body.measure, target=body.target_value, current=current):
        raise ApiError(
            422,
            "target_not_reachable",
            f"{config['label']} is {current:g} {config['unit']} now — a goal has to ask for a change "
            f"in the direction this measure moves",
        )
    if body.target_date and body.target_date <= today:
        raise ApiError(422, "target_date_past", "the target date has already gone")

    # Set by the student is agreed at once; proposed by a parent waits for her (AC-G1).
    by_student = principal.role == "student"
    row = Goal(
        tenant_id=principal.tenant_id,
        student_id=student_id,
        kind=body.measure,
        statement=body.statement,
        measure=body.measure,
        target_value=body.target_value,
        baseline_value=current,
        subject_id=body.subject_id,
        target_date=body.target_date,
        status="active" if by_student else "proposed",
        proposed_by_role=principal.role,
        agreed_at=now if by_student else None,
        rule_version=rules.RULE_VERSION,
    )
    s.add(row)
    s.flush()
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="goal.created",
        entity_type="goal",
        entity_id=row.id,
        student_id=student_id,
        meta={"measure": row.measure, "target": row.target_value, "status": row.status},
    )
    names = curriculum.subject_summaries(s, [row.subject_id] if row.subject_id else [])
    return _out(s, row, today=today, subject_names={k: v.name for k, v in names.items()})


def _goal_row(s: Session, principal: Principal, goal_id: UUID) -> Goal:
    row = s.get(Goal, goal_id)
    if row is None:
        raise not_found("goal")
    require_student_access(principal, row.student_id, SCOPE)
    return row


def agree(s: Session, principal: Principal, goal_id: UUID, *, now: datetime) -> GoalOut:
    """Only the student agrees to a goal. A parent cannot agree on her behalf (AC-G1)."""
    row = _goal_row(s, principal, goal_id)
    if principal.role != "student":
        raise forbidden(message="a goal is agreed by the student, not for her")
    if row.status == "proposed":
        row.status = "active"
        row.agreed_at = now
        s.flush()
        audit.record(
            s,
            tenant_id=row.tenant_id,
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            action="goal.agreed",
            entity_type="goal",
            entity_id=row.id,
            student_id=row.student_id,
        )
    today = local_date(now, identity.student_timezone(s, row.student_id))
    names = curriculum.subject_summaries(s, [row.subject_id] if row.subject_id else [])
    return _out(s, row, today=today, subject_names={k: v.name for k, v in names.items()})


def drop(s: Session, principal: Principal, goal_id: UUID, *, now: datetime) -> GoalOut:
    """Either of them may let a goal go — a goal nobody believes in is worse than no goal."""
    row = _goal_row(s, principal, goal_id)
    if row.status in ("proposed", "active"):
        row.status = "dropped"
        s.flush()
        audit.record(
            s,
            tenant_id=row.tenant_id,
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            action="goal.dropped",
            entity_type="goal",
            entity_id=row.id,
            student_id=row.student_id,
        )
    today = local_date(now, identity.student_timezone(s, row.student_id))
    names = curriculum.subject_summaries(s, [row.subject_id] if row.subject_id else [])
    return _out(s, row, today=today, subject_names={k: v.name for k, v in names.items()})


def settle_achieved(s: Session, student_id: UUID, *, now: datetime | None = None) -> int:
    """Mark active goals whose measure has reached its target. Derived, so nobody has to claim it."""
    now = now or datetime.now(UTC)
    today = local_date(now, identity.student_timezone(s, student_id))
    changed = 0
    readings: dict[tuple[str, UUID | None], float] = {}
    for row in s.scalars(select(Goal).where(Goal.student_id == student_id, Goal.status == "active")):
        key = (row.measure, row.subject_id)
        if key not in readings:
            readings[key] = _reading(
                s, student_id=student_id, measure=row.measure, subject_id=row.subject_id, today=today
            )
        progress = rules.progress(
            measure=row.measure,  # type: ignore[arg-type]
            current=readings[key],
            target=row.target_value,
            baseline=row.baseline_value,
            target_date=row.target_date,
            today=today,
        )
        if progress.reached:
            row.status = "achieved"
            changed += 1
    if changed:
        s.flush()
    return changed


def counts_by_status(s: Session, student_id: UUID) -> dict[str, int]:
    found: dict[str, int] = defaultdict(int)
    for (status,) in s.execute(select(Goal.status).where(Goal.student_id == student_id)).all():
        found[status] += 1
    return dict(found)
