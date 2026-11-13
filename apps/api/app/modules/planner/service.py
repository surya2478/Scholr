"""Planner service: gather the day's signals, build the plan (planner.engine), persist it, track item status."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.assessment import service as assessment
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.evaluation import service as evaluation
from app.modules.events import service as events
from app.modules.external_training import service as external_training
from app.modules.identity import service as identity
from app.modules.learn import labels
from app.modules.learn import service as learn
from app.modules.mastery import service as mastery
from app.modules.mistakes import service as mistakes
from app.modules.planner import daily, engine, sessions
from app.modules.planner.models import DailyPractice, PlanItem, StudyPlan
from app.modules.planner.schemas import (
    DailyItemOut,
    DailyPracticeOut,
    DroppedOut,
    PlanItemOut,
    PlanOut,
    SessionDoorOut,
    TimelineBlockOut,
    TomorrowTopicOut,
)
from app.modules.studies import service as studies
from app.modules.subjects import service as subjects
from app.tools.dates import RecurrenceError, local_date, local_day_start, occurs_on

REASONS_FILE = Path(__file__).with_name("reasons.yaml")
REASON_DETAIL_MAX = 300  # plan_item.reason_detail
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


@lru_cache
def reasons() -> dict[str, dict[str, str]]:
    return yaml.safe_load(REASONS_FILE.read_text(encoding="utf-8"))


def _signals(
    s: Session,
    student_id: UUID,
    day: date,
    now: datetime,
    reinforcement: Sequence[UUID] = (),  # best first
) -> list[engine.ObjectiveSignal]:
    subject_ids = {e.subject_id for e in enrollment.list_enrollments(s, [student_id])}
    flags: dict[UUID, dict[str, Any]] = defaultdict(dict)

    for m in mastery.list_mastery(s, student_id=student_id):
        flags[m.objective_id].update(mastery_level=m.level, retention_risk=m.retention_risk)
    for p in mistakes.list_mistakes(s, student_id=student_id):
        if p.objective_id is None or p.status == "resolved":
            continue
        current = flags[p.objective_id].get("mistake_severity")
        if current is None or _SEVERITY_RANK[p.severity] > _SEVERITY_RANK[current]:
            flags[p.objective_id]["mistake_severity"] = p.severity
    window_end = now + timedelta(days=engine.ASSESSMENT_WINDOW_DAYS)
    for upcoming in enrollment.list_upcoming_assessments(s, student_id=student_id, start=now, end=window_end):
        for objective_id in upcoming.objective_ids:
            flags[objective_id]["assessment_due"] = True
    topic_ids = [
        t for entry in enrollment.teaching_entries_on(s, student_id=student_id, day=day) for t in entry.topic_ids
    ]
    for objective in curriculum.objectives_under_topics(s, topic_ids):
        flags[objective.id]["school_topic"] = True
    # Phase 3: the external IIT classes never become plan items themselves — what they point at does.
    for rank, objective_id in enumerate(reinforcement):
        flags[objective_id].update(external_weakness=True, external_rank=rank)

    summaries = curriculum.objective_summaries(s, list(flags))
    return [
        engine.ObjectiveSignal(objective_id=oid, subject_id=summaries[oid].subject_id, **values)
        for oid, values in flags.items()
        if oid in summaries and summaries[oid].subject_id in subject_ids
    ]


def _generate(s: Session, *, tenant_id: UUID, student_id: UUID, day: date, now: datetime) -> StudyPlan:
    capacity = engine.day_capacity(
        day,
        enrollment.availability(s, student_id=student_id),
        [
            engine.CommitmentIn(c.title, c.rrule, c.duration_min)
            for c in enrollment.list_commitments(s, student_id=student_id)
        ],
    )
    reinforcement_reasons = {
        # Trimmed to the column width: a long lesson title must not fail the whole day's plan.
        target.objective_id: target.reason[:REASON_DETAIL_MAX]
        # Only what Scholr can actually set work in. A planned subject can be named on the IIT page as
        # something to revise, but a plan item with no questions behind it is a dead end.
        for target in external_training.reinforcement(s, student_id=student_id, today=day, practicable_only=True)
    }
    signals = _signals(s, student_id, day, now, reinforcement=list(reinforcement_reasons))
    control = studies.control_objective_ids(s, student_id=student_id, at=now)
    draft = engine.build_plan(signals, capacity_minutes=capacity.minutes, control_objectives=control)
    plan = StudyPlan(
        tenant_id=tenant_id,
        student_id=student_id,
        plan_date=day,
        generator_version=engine.GENERATOR_VERSION,
        capacity_minutes=capacity.minutes,
        inputs_snapshot={
            "generated_at": now.isoformat(),
            "capacity": {
                "available": capacity.available,
                "commitments": capacity.commitments,
                "buffer": capacity.buffer,
                "lighter_day": capacity.lighter_day,
                "unsupported_rules": list(capacity.unsupported_rules),
            },
            "signals": len(signals),
            "excluded_control_objectives": draft.excluded_control,
            "overload": draft.overload,
            "dropped": [
                {"objective_id": str(e.objective_id), "kind": e.kind, "reason_code": e.reason_code}
                for e in draft.dropped
            ],
        },
    )
    s.add(plan)
    s.flush()
    for position, entry in enumerate(draft.entries):
        s.add(
            PlanItem(
                tenant_id=tenant_id,
                student_id=student_id,
                plan_id=plan.id,
                subject_id=entry.subject_id,
                objective_id=entry.objective_id,
                kind=entry.kind,
                position=position,
                est_minutes=entry.est_minutes,
                priority=entry.priority,
                reason_code=entry.reason_code,
                reason_detail=reinforcement_reasons.get(entry.objective_id) if entry.kind == "reinforcement" else None,
            )
        )
    s.flush()
    return plan


def _plan_for(s: Session, student_id: UUID, day: date) -> StudyPlan | None:
    return s.scalar(
        select(StudyPlan).where(
            StudyPlan.student_id == student_id,
            StudyPlan.plan_date == day,
            StudyPlan.generator_version == engine.GENERATOR_VERSION,
        )
    )


def _fixed_blocks(s: Session, student_id: UUID, day: date) -> list[engine.FixedBlock]:
    """Commitments that fall on this day, at their own clock times (school, IIT classes)."""
    blocks = []
    for commitment in enrollment.list_commitments(s, student_id=student_id):
        if not commitment.start_time:
            continue
        try:
            if not occurs_on(commitment.rrule, day):
                continue
        except RecurrenceError:
            continue
        hour, minute = (int(part) for part in commitment.start_time.split(":"))
        blocks.append(
            engine.FixedBlock(commitment.title, commitment.notes, time(hour, minute), commitment.duration_min)
        )
    return blocks


def _timeline(
    s: Session,
    plan: StudyPlan,
    items: Sequence[PlanItem],
    item_outs: Sequence[PlanItemOut],
) -> list[TimelineBlockOut]:
    entries = [
        (out.kind, out.subject_name or "Study", out.objective_statement or out.reason, out.est_minutes)
        for out in item_outs
    ]
    blocks = engine.schedule_day(
        entries, _fixed_blocks(s, plan.student_id, plan.plan_date), weekend=plan.plan_date.weekday() >= 5
    )
    return [
        TimelineBlockOut(
            kind=block.kind,
            title=block.title,
            detail=block.detail,
            minutes=block.minutes,
            start=block.start,
            end=block.end,
            status=None if block.item_index is None else items[block.item_index].status,
            plan_item_id=None if block.item_index is None else items[block.item_index].id,
        )
        for block in blocks
    ]


ANSWER_FIRST = "Answer at least one question on this topic first. Reading the notes is not the same as using them."


def _waiting_for_an_answer(s: Session, plan: StudyPlan, items: Sequence[PlanItem]) -> set[UUID]:
    """Open plan items on a topic with questions she has not answered a question on since the plan's day began.

    Reading a topic is not finishing it: an item on a topic that has questions counts as done only once she has
    answered one of them that day. A topic with no questions to try (a lessons-only subject, a topic the bank does
    not cover) has nothing else to ask of her, so it can be marked done as before.
    """
    open_items = [i for i in items if i.objective_id and i.status in ("planned", "in_progress")]
    if not open_items:
        return set()
    with_questions = {
        oid for oid in {i.objective_id for i in open_items} if oid and assessment.items_for_objective(s, oid)
    }
    if not with_questions:
        return set()
    since = local_day_start(plan.plan_date, identity.student_timezone(s, plan.student_id))
    answered: set[UUID] = set()
    for ev in events.list_events(
        s, student_id=plan.student_id, types=["attempt_submitted"], objective_ids=list(with_questions), since=since
    ):
        answered.update(ev.objective_ids)
    return {i.id for i in open_items if i.objective_id in with_questions and i.objective_id not in answered}


def _out(s: Session, plan: StudyPlan) -> PlanOut:
    items = s.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id).order_by(PlanItem.position)).all()
    waiting = _waiting_for_an_answer(s, plan, items)
    snapshot = plan.inputs_snapshot or {}
    dropped = snapshot.get("dropped", [])
    objective_ids = [i.objective_id for i in items if i.objective_id] + [UUID(d["objective_id"]) for d in dropped]
    objectives = curriculum.objective_summaries(s, objective_ids)
    subject_names = {
        sid: sub.name for sid, sub in curriculum.subject_summaries(s, [i.subject_id for i in items]).items()
    }
    texts = reasons()
    notices = [
        texts["notices"][code]
        for code in engine.notice_codes(
            overload=bool(snapshot.get("overload")),
            lighter_day=bool((snapshot.get("capacity") or {}).get("lighter_day")),
            capacity_minutes=plan.capacity_minutes,
        )
    ]
    item_outs = [
        PlanItemOut(
            id=i.id,
            position=i.position,
            subject_id=i.subject_id,
            subject_name=subject_names.get(i.subject_id, ""),
            objective_id=i.objective_id,
            objective_code=objectives[i.objective_id].code if i.objective_id in objectives else None,
            objective_statement=objectives[i.objective_id].statement if i.objective_id in objectives else None,
            kind=i.kind,
            est_minutes=i.est_minutes,
            priority=i.priority,
            reason_code=i.reason_code,
            reason=i.reason_detail or texts["reasons"].get(i.reason_code, ""),
            status=i.status,
            needs_answer=i.id in waiting,
        )
        for i in items
    ]
    return PlanOut(
        id=plan.id,
        plan_date=plan.plan_date,
        capacity_minutes=plan.capacity_minutes,
        planned_minutes=sum(i.est_minutes for i in items),
        items=item_outs,
        timeline=_timeline(s, plan, items, item_outs),
        dropped=[
            DroppedOut(
                objective_code=objectives[UUID(d["objective_id"])].code
                if UUID(d["objective_id"]) in objectives
                else None,
                kind=d["kind"],
                reason_code=d["reason_code"],
            )
            for d in dropped
        ],
        notices=notices,
    )


def _today(s: Session, student_id: UUID, now: datetime) -> date:
    return local_date(now, identity.student_timezone(s, student_id))


def _ensure_plan(s: Session, *, tenant_id: UUID, student_id: UUID, day: date, now: datetime) -> StudyPlan:
    plan = _plan_for(s, student_id, day)
    if plan is None:
        try:
            with s.begin_nested():  # two first-reads of the day can race; the unique key keeps one plan
                plan = _generate(s, tenant_id=tenant_id, student_id=student_id, day=day, now=now)
        except IntegrityError:
            plan = _plan_for(s, student_id, day)
            if plan is None:
                raise
    return plan


def plan_today(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> PlanOut:
    require_student_access(principal, student_id, "plans")
    day = _today(s, student_id, now)
    return _out(s, _ensure_plan(s, tenant_id=principal.tenant_id, student_id=student_id, day=day, now=now))


# --- daily practice set (docs/STUDENT-APP.md step 4) ------------------------------------------------------------

_MISTAKE_REASON = {"high": "open_mistake_high", "medium": "open_mistake_medium", "low": "open_mistake_medium"}
_RETENTION_REASON = {"high": "retention_high", "medium": "retention_medium"}


def _taught_subjects(s: Session, student_id: UUID) -> set[UUID]:
    enrolled = {e.subject_id for e in enrollment.list_enrollments(s, [student_id])}
    out = set()
    for subject in curriculum.subject_summaries(s, list(enrolled)).values():
        try:
            if subjects.config_for(subject.code).taught_here:
                out.add(subject.id)
        except subjects.SubjectConfigError:
            continue
    return out


def _plan_wants(s: Session, plan: StudyPlan) -> list[daily.Want]:
    return [
        daily.Want(item.objective_id, item.reason_code)
        for item in s.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id).order_by(PlanItem.position))
        if item.objective_id is not None
    ]


def _state_wants(s: Session, student_id: UUID) -> list[daily.Want]:
    """What her record alone asks for, in order of claim: open mistakes, retention risk, then lessons only read.

    Split from the plan's wants so tomorrow's preview can be built without generating tomorrow's plan.
    """
    wants: list[daily.Want] = []
    open_mistakes = [
        m for m in mistakes.list_mistakes(s, student_id=student_id) if m.objective_id and m.status != "resolved"
    ]
    for m in sorted(open_mistakes, key=lambda m: -_SEVERITY_RANK[m.severity]):
        wants.append(daily.Want(m.objective_id, _MISTAKE_REASON[m.severity]))  # type: ignore[arg-type]
    states = mastery.list_mastery(s, student_id=student_id)
    for risk in ("high", "medium"):
        wants.extend(daily.Want(m.objective_id, _RETENTION_REASON[risk]) for m in states if m.retention_risk == risk)
    wants.extend(
        daily.Want(m.objective_id, "lesson_read") for m in states if m.level == mastery.MasteryLevel.INTRODUCED
    )
    return wants


def _daily_wants(s: Session, plan: StudyPlan, student_id: UUID) -> list[daily.Want]:
    return _plan_wants(s, plan) + _state_wants(s, student_id)


def _servable(
    s: Session, wants: Sequence[daily.Want], student_id: UUID
) -> tuple[list[daily.Want], dict[UUID, list[daily.Candidate]], dict[UUID, curriculum.ObjectiveSummary]]:
    """Keep the wants that name a topic in a taught subject, with that topic's bank items."""
    taught = _taught_subjects(s, student_id)
    summaries = curriculum.objective_summaries(s, [w.objective_id for w in wants])
    kept = [w for w in wants if w.objective_id in summaries and summaries[w.objective_id].subject_id in taught]
    candidates = {
        oid: [daily.Candidate(i.id, i.marks) for i in assessment.items_for_objective(s, oid)]
        for oid in {w.objective_id for w in kept}
    }
    return kept, candidates, summaries


def _doors(s: Session, *, student_id: UUID, items: list[DailyItemOut], now: datetime) -> list[SessionDoorOut]:
    """The three ways into today's work, each with the minutes its own content actually takes.

    All three are always returned, a closed one carrying the reason it is closed: a door that hides itself reads
    as a feature that does not exist (AC-U13 made the same call for the parts of a topic page).
    """
    texts = reasons()
    door_text, closed_text = texts["doors"], texts["closed"]
    pool = [
        sessions.Item(
            item_id=x.item_id,
            objective_id=x.objective_id,
            marks=x.marks,
            reason_code=x.reason_code,
            to_do=x.status == "to_do",
        )
        for x in items
    ]
    left_items = sessions.to_do(pool)
    empty_reason = "nothing_today" if not pool else "set_finished"

    quick = sessions.quick_pick(pool)
    out = [
        SessionDoorOut(
            key="quick",
            text=door_text["quick"],
            minutes=sessions.minutes_for(quick),
            questions=len(quick),
            open=bool(quick),
            closed_reason=None if quick else closed_text[empty_reason if not left_items else "nothing_due"],
        ),
        SessionDoorOut(
            key="today",
            text=door_text["today"],
            minutes=sessions.minutes_for(left_items),
            questions=len(left_items),
            open=bool(left_items),
            closed_reason=None if left_items else closed_text[empty_reason],
        ),
    ]

    # The first of today's topics that still has something to read or try. The first by claim can be one she has
    # already read and practised (seen on her own record, 25 Oct 2026), so the door looks past it.
    candidates = sessions.deep_candidates(pool)
    objective_id, minutes, parts = None, 0, []
    for candidate in candidates[: sessions.MAX_DEEP_LOOKUPS]:
        part = learn.next_part(s, candidate, student_id=student_id, now=now)
        if part is not None:
            label, minutes, after = part
            objective_id, parts = candidate, [label, *after]
            break
    topic = next((x for x in items if x.objective_id == objective_id), None) if objective_id else None
    # Why it is closed, truthfully: the set is empty, or she has finished it, or today's topics have nothing left
    # on their pages and what remains is the questions themselves.
    deep_closed = empty_reason if not left_items else "nothing_left"

    out.append(
        SessionDoorOut(
            key="deep",
            text=door_text["deep"],
            minutes=minutes,
            questions=0,
            objective_id=objective_id,
            objective_code=topic.objective_code if topic else None,
            objective_statement=topic.objective_statement if topic else None,
            parts=parts,
            open=objective_id is not None,
            closed_reason=None if objective_id is not None else closed_text[deep_closed],
        )
    )
    return out


def _tomorrow_topics(s: Session, *, student_id: UUID, day: date, now: datetime) -> list[TomorrowTopicOut]:
    """The topics tomorrow's set would start from, by the same rule over the record as it stands now.

    Tomorrow's plan does not exist yet and generating it would write rows for a day that has not started, so this
    takes her state wants only — open mistakes, retention risk, lessons only read. A topic is named only if it still
    has a question she has not answered inside the rule's recent window, so the preview cannot promise work that is
    not there. Tomorrow's plan may add topics on top, which is why the UI says it can change.
    """
    tomorrow = day + timedelta(days=1)
    wants, candidates, summaries = _servable(s, _state_wants(s, student_id), student_id)
    picks = daily.choose(
        wants,
        candidates,
        recent=assessment.recent_item_ids(
            s, student_id=student_id, since=now + timedelta(days=1) - timedelta(days=daily.RECENT_DAYS)
        ),
        excluded=studies.control_objective_ids(s, student_id=student_id, at=now),
        seed=f"{student_id}:{tomorrow.isoformat()}",
        size=daily.PREVIEW_SIZE,
    )
    subject_names = {
        x.id: x.name for x in curriculum.subject_summaries(s, [o.subject_id for o in summaries.values()]).values()
    }
    texts = reasons()["reasons"]
    out: list[TomorrowTopicOut] = []
    for pick in picks:
        objective = summaries.get(pick.objective_id)
        if objective is None or any(t.objective_id == pick.objective_id for t in out):
            continue  # one line per topic, however many of its questions the rule would set
        out.append(
            TomorrowTopicOut(
                subject_id=objective.subject_id,
                subject_name=subject_names.get(objective.subject_id, ""),
                objective_id=pick.objective_id,
                objective_code=objective.code,
                objective_statement=objective.statement,
                reason_code=pick.reason_code,
                reason=texts.get(pick.reason_code, ""),
            )
        )
    return out


def _build_daily(s: Session, *, tenant_id: UUID, student_id: UUID, day: date, now: datetime) -> DailyPractice:
    plan = _ensure_plan(s, tenant_id=tenant_id, student_id=student_id, day=day, now=now)
    wants, candidates, _ = _servable(s, _daily_wants(s, plan, student_id), student_id)
    picks = daily.choose(
        wants,
        candidates,
        recent=assessment.recent_item_ids(s, student_id=student_id, since=now - timedelta(days=daily.RECENT_DAYS)),
        excluded=studies.control_objective_ids(s, student_id=student_id, at=now),
        seed=f"{student_id}:{day.isoformat()}",
    )
    row = DailyPractice(
        tenant_id=tenant_id,
        student_id=student_id,
        practice_date=day,
        rule_version=daily.RULE_VERSION,
        items=[
            {"item_id": str(p.item_id), "objective_id": str(p.objective_id), "reason_code": p.reason_code}
            for p in picks
        ],
    )
    s.add(row)
    s.flush()
    return row


def daily_practice(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> DailyPracticeOut:
    """Today's practice set: built on first request and then fixed for the day; progress read from her attempts."""
    require_student_access(principal, student_id, "plans")
    day = _today(s, student_id, now)
    row = s.scalar(
        select(DailyPractice).where(DailyPractice.student_id == student_id, DailyPractice.practice_date == day)
    )
    if row is None:
        try:
            with s.begin_nested():  # same race as the plan: the unique key keeps one set a day
                row = _build_daily(s, tenant_id=principal.tenant_id, student_id=student_id, day=day, now=now)
        except IntegrityError:
            row = s.scalar(
                select(DailyPractice).where(DailyPractice.student_id == student_id, DailyPractice.practice_date == day)
            )
            if row is None:
                raise

    item_ids = [UUID(x["item_id"]) for x in row.items]
    objective_ids = [UUID(x["objective_id"]) for x in row.items]
    briefs = assessment.item_briefs(s, item_ids)
    objectives = curriculum.objective_summaries(s, objective_ids)
    subject_names = {
        x.id: x.name for x in curriculum.subject_summaries(s, [o.subject_id for o in objectives.values()]).values()
    }
    since = local_day_start(day, identity.student_timezone(s, student_id))
    attempts = assessment.latest_attempts(s, student_id=student_id, item_ids=item_ids, since=since)
    marks = evaluation.marks_for_attempts(s, list(attempts.values()))
    texts = reasons()["reasons"]

    out: list[DailyItemOut] = []
    for entry, item_id, objective_id in zip(row.items, item_ids, objective_ids, strict=True):
        brief, objective = briefs.get(item_id), objectives.get(objective_id)
        if brief is None or objective is None:  # withdrawn from the bank since the set was built
            continue
        attempt_id = attempts.get(item_id)
        mark = marks.get(attempt_id) if attempt_id else None
        if attempt_id is None:
            status = "to_do"
        elif mark is None:
            status = "answered"
        else:
            status = "provisional" if mark.status == "needs_review" else "marked"
        out.append(
            DailyItemOut(
                item_id=item_id,
                subject_id=objective.subject_id,
                subject_name=subject_names.get(objective.subject_id, ""),
                objective_id=objective_id,
                objective_code=objective.code,
                objective_statement=objective.statement,
                source_ref=brief.source_ref,
                label=labels.item_label(brief.source_ref, brief.origin),
                marks=brief.marks,
                reason_code=entry["reason_code"],
                reason=texts.get(entry["reason_code"], ""),
                status=status,  # type: ignore[arg-type]
                evaluation_id=mark.evaluation_id if mark else None,
                marks_awarded=mark.marks_awarded if mark else None,
            )
        )
    plan = _plan_for(s, student_id, day)
    done = sum(1 for x in out if x.status != "to_do")
    finished = bool(out) and done == len(out)
    return DailyPracticeOut(
        practice_date=day,
        rule_version=row.rule_version,
        items=out,
        done=done,
        total=len(out),
        tomorrow=_tomorrow_topics(s, student_id=student_id, day=day, now=now) if finished else [],
        doors=_doors(s, student_id=student_id, items=out, now=now),
        notice=None if out else "Nothing to practise today — your plan has no topics with questions yet.",
        answering_minutes=round(assessment.seconds_answering_since(s, student_id=student_id, since=since) / 60),
        planned_minutes=plan.capacity_minutes if plan else None,
        external_minutes=external_training.minutes_on(s, student_id=student_id, day=day),
    )


def regenerate(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> PlanOut:
    """Rebuild today's plan (items already completed keep their status only if the same item is planned again)."""
    require_student_access(principal, student_id, "plans")
    day = _today(s, student_id, now)
    existing = _plan_for(s, student_id, day)
    finished: dict[tuple[UUID | None, str], str] = {}
    if existing is not None:
        for item in s.scalars(select(PlanItem).where(PlanItem.plan_id == existing.id)):
            if item.status in ("completed", "skipped"):
                finished[(item.objective_id, item.kind)] = item.status
        s.delete(existing)
        s.flush()
    plan = _generate(s, tenant_id=principal.tenant_id, student_id=student_id, day=day, now=now)
    for item in s.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id)):
        if (item.objective_id, item.kind) in finished:
            item.status = finished[(item.objective_id, item.kind)]
    s.flush()
    return _out(s, plan)


def update_item(s: Session, principal: Principal, item_id: UUID, status: str, *, now: datetime) -> PlanOut:
    item = s.get(PlanItem, item_id)
    if item is None:
        raise not_found("plan item")
    if principal.role != "student" or principal.student_id != item.student_id:
        raise ApiError(403, "forbidden", "only the student can update their plan items")
    if item.status in ("completed", "skipped") and status != item.status:
        raise ApiError(409, "item_closed", "this plan item is already finished")
    plan = s.get(StudyPlan, item.plan_id)
    assert plan is not None
    if status == "completed" and item.status != "completed" and item.id in _waiting_for_an_answer(s, plan, [item]):
        raise ApiError(409, "answer_first", ANSWER_FIRST)
    previous, item.status = item.status, status
    if status in ("completed", "skipped") and previous != status:
        events.append(
            s,
            tenant_id=item.tenant_id,
            student_id=item.student_id,
            event_type=f"plan_item_{status}",
            occurred_at=now,
            payload={"plan_item_id": item.id},
            subject_id=item.subject_id,
            objective_ids=[item.objective_id] if item.objective_id else [],
            ref_type="plan_item",
            ref_id=item.id,
        )
    s.flush()
    return _out(s, plan)


def start_of_local_day(day: date) -> datetime:
    return datetime.combine(day, time.min)


def item_counts(s: Session, *, student_id: UUID, start: date, end: date) -> dict[str, int]:
    """Plan items by status for plans dated start..end (inclusive), current generator only."""
    rows = s.execute(
        select(PlanItem.status, func.count(PlanItem.id))
        .join(StudyPlan, StudyPlan.id == PlanItem.plan_id)
        .where(
            StudyPlan.student_id == student_id,
            StudyPlan.generator_version == engine.GENERATOR_VERSION,
            StudyPlan.plan_date >= start,
            StudyPlan.plan_date <= end,
        )
        .group_by(PlanItem.status)
    ).all()
    return {status: count for status, count in rows}
