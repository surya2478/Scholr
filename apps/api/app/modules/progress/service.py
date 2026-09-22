"""Progress: read-only summaries for the student and their guardians, composed from other modules' services.

Nothing here is stored; every number is derived on request from mastery, mistake patterns, plans and events.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.rbac import Principal, can_access_student, require_role, require_student_access
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.evaluation import service as evaluation
from app.modules.events import service as events
from app.modules.identity import service as identity
from app.modules.mastery import service as mastery
from app.modules.mastery.rules import LEVEL_NAMES, MasteryLevel
from app.modules.mastery.schemas import MasteryOut
from app.modules.mistakes import service as mistakes
from app.modules.mistakes.schemas import MistakeOut
from app.modules.planner import service as planner
from app.modules.progress import metacognition as metacognition_mod
from app.modules.progress.schemas import (
    FocusOut,
    GuardianOverviewOut,
    MetacognitionOut,
    MonthlySummaryOut,
    MonthSubjectOut,
    MonthTotalsOut,
    ProgressSummaryOut,
    SafetyOverviewOut,
    SubjectProgressOut,
    SuggestionOut,
    TrendDayOut,
    TrendsOut,
    TrendSubjectOut,
    TrendWeekOut,
    UpcomingBriefOut,
    WeekOut,
    WinOut,
)
from app.modules.safety import service as safety
from app.tools.dates import local_date

WEEK_DAYS = 7
INDEPENDENT_HELP_LEVEL = 1  # at most a nudge
WORKED_SOLUTION_LEVEL = 5
TREND_WEEKS = 8
SOON_DAYS = 7
FOCUS_LIMIT = 5
WINS_LIMIT = 5
UPCOMING_DAYS = 14
SEVERITY_NAMES = {1: "low", 2: "medium", 3: "high"}


# --- pure aggregation -----------------------------------------------------------------------------------------


def level_counts(objectives_total: int, rows: Sequence[MasteryOut]) -> dict[str, int]:
    counts = {name: 0 for name in LEVEL_NAMES.values()}
    for row in rows:
        counts[row.level_name] += 1
    counts[LEVEL_NAMES[MasteryLevel.NOT_INTRODUCED]] += max(0, objectives_total - len(rows))
    return counts


def subject_progress(
    *,
    subject_id: UUID,
    subject_name: str,
    objectives_total: int,
    mastery_rows: Sequence[MasteryOut],
    open_mistakes: Sequence[MistakeOut],
    include_mastery: bool,
) -> SubjectProgressOut:
    rows = [r for r in mastery_rows if r.subject_id == subject_id] if include_mastery else []
    patterns = [m for m in open_mistakes if m.subject_id == subject_id]
    return SubjectProgressOut(
        subject_id=subject_id,
        subject_name=subject_name,
        objectives_total=objectives_total,
        level_counts=level_counts(objectives_total, rows) if include_mastery else {},
        competent_or_better=sum(1 for r in rows if r.level >= MasteryLevel.COMPETENT),
        retention_high=sum(1 for r in rows if r.retention_risk == "high"),
        open_mistakes=len(patterns),
        high_severity_mistakes=sum(1 for m in patterns if m.severity == "high"),
    )


def focus_items(
    mastery_rows: Sequence[MasteryOut], open_mistakes: Sequence[MistakeOut], *, limit: int = FOCUS_LIMIT
) -> list[FocusOut]:
    """High-severity mistakes first (most recent first), then objectives at high retention risk (oldest first)."""
    items = [
        FocusOut(
            kind="mistake",
            subject_id=m.subject_id,
            objective_id=m.objective_id,
            objective_code=m.objective_code,
            label=m.description,
        )
        for m in sorted(open_mistakes, key=lambda m: m.last_seen, reverse=True)
        if m.severity == "high"
    ]
    fading = sorted(
        (r for r in mastery_rows if r.retention_risk == "high"),
        key=lambda r: (r.last_demonstrated_at is not None, r.last_demonstrated_at or datetime.min),
    )
    items += [
        FocusOut(
            kind="retention",
            subject_id=r.subject_id,
            objective_id=r.objective_id,
            objective_code=r.objective_code,
            label=r.objective_statement,
        )
        for r in fading
    ]
    return items[:limit]


def recent_wins(mastery_rows: Sequence[MasteryOut], *, since: datetime, limit: int = WINS_LIMIT) -> list[WinOut]:
    wins = [
        r
        for r in mastery_rows
        if r.level >= MasteryLevel.COMPETENT and r.last_demonstrated_at is not None and r.last_demonstrated_at >= since
    ]
    wins.sort(key=lambda r: (-r.level, -(r.last_demonstrated_at.timestamp() if r.last_demonstrated_at else 0)))
    return [
        WinOut(
            subject_id=r.subject_id,
            objective_id=r.objective_id,
            objective_code=r.objective_code,
            objective_statement=r.objective_statement,
            level_name=r.level_name,
            last_demonstrated_at=r.last_demonstrated_at,  # type: ignore[arg-type]
        )
        for r in wins[:limit]
    ]


def help_mix(window_events: Sequence[events.EventView]) -> tuple[int, int, int]:
    """Marked answers by how they were reached: (without help, with hints, worked solution)."""
    counts = [0, 0, 0]
    for ev in window_events:
        if ev.type != "attempt_evaluated":
            continue
        level = int(ev.payload.get("help_level") or 0)
        counts[0 if level <= INDEPENDENT_HELP_LEVEL else 1 if level < WORKED_SOLUTION_LEVEL else 2] += 1
    return counts[0], counts[1], counts[2]


def week_stats(
    recent_events: Sequence[events.EventView], plan_counts: dict[str, int], *, since: date, timezone: str
) -> WeekOut:
    without_help, _, _ = help_mix(recent_events)
    return WeekOut(
        since=since,
        attempts_evaluated=sum(1 for ev in recent_events if ev.type == "attempt_evaluated"),
        answers_without_help=without_help,
        mistakes_fixed=sum(1 for ev in recent_events if ev.type == "mistake_resolved"),
        study_minutes=_study_minutes(recent_events),
        active_days=len({local_date(ev.occurred_at, timezone) for ev in recent_events}),
        plan_items_total=sum(plan_counts.values()),
        plan_items_completed=plan_counts.get("completed", 0),
        plan_items_skipped=plan_counts.get("skipped", 0),
    )


# --- service --------------------------------------------------------------------------------------------------


def _summary(s: Session, *, student_id: UUID, now: datetime, include_mastery: bool) -> ProgressSummaryOut:
    since = now - timedelta(days=WEEK_DAYS)
    subject_ids = sorted({e.subject_id for e in enrollment.list_enrollments(s, [student_id])})
    subjects = curriculum.subject_summaries(s, subject_ids)
    totals = curriculum.objective_counts(s, subject_ids)
    mastery_rows = mastery.list_mastery(s, student_id=student_id) if include_mastery else []
    open_mistakes = [m for m in mistakes.list_mistakes(s, student_id=student_id) if m.status in mistakes.UNRESOLVED]
    timezone = identity.student_timezone(s, student_id)
    today = local_date(now, timezone)
    week_start = today - timedelta(days=WEEK_DAYS - 1)
    return ProgressSummaryOut(
        student_id=student_id,
        generated_at=now,
        subjects=sorted(
            (
                subject_progress(
                    subject_id=sid,
                    subject_name=subjects[sid].name if sid in subjects else "",
                    objectives_total=totals.get(sid, 0),
                    mastery_rows=mastery_rows,
                    open_mistakes=open_mistakes,
                    include_mastery=include_mastery,
                )
                for sid in subject_ids
            ),
            key=lambda p: p.subject_name,
        ),
        week=week_stats(
            events.list_events(s, student_id=student_id, since=since),
            planner.item_counts(s, student_id=student_id, start=week_start, end=today),
            since=week_start,
            timezone=timezone,
        ),
        focus=focus_items(mastery_rows, open_mistakes),
        recent_wins=recent_wins(mastery_rows, since=since),
    )


def summary(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> ProgressSummaryOut:
    require_student_access(principal, student_id, "progress")
    include_mastery = can_access_student(principal, student_id, "mastery")
    return _summary(s, student_id=student_id, now=now, include_mastery=include_mastery)


def guardian_overview(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> GuardianOverviewOut:
    require_role(principal, "guardian", "admin")
    require_student_access(principal, student_id, "progress")

    def allowed(scope: str) -> bool:
        return can_access_student(principal, student_id, scope)

    timezone = identity.student_timezone(s, student_id)
    safety_out = None
    if allowed("safety"):
        open_incidents = [
            i for i in safety.list_incidents(s, principal, student_id=student_id) if i.escalation_status != "resolved"
        ]
        by_severity = {name: 0 for name in SEVERITY_NAMES.values()}
        for incident in open_incidents:
            by_severity[SEVERITY_NAMES[incident.severity]] += 1
        safety_out = SafetyOverviewOut(
            open_total=len(open_incidents),
            open_by_severity=by_severity,
            latest_open_at=max((i.occurred_at for i in open_incidents), default=None),
        )
    summary = _summary(s, student_id=student_id, now=now, include_mastery=allowed("mastery"))
    secure_objectives = (
        {m.objective_id for m in mastery.list_mastery(s, student_id=student_id) if m.level >= MasteryLevel.COMPETENT}
        if allowed("mastery")
        else None
    )
    upcoming = None
    if allowed("plans"):
        rows = enrollment.list_upcoming_assessments(
            s, student_id=student_id, start=now, end=now + timedelta(days=UPCOMING_DAYS)
        )
        names = curriculum.subject_summaries(s, [u.subject_id for u in rows])
        upcoming = [
            UpcomingBriefOut(
                subject_id=u.subject_id,
                subject_name=names[u.subject_id].name if u.subject_id in names else "",
                title=u.title,
                due_at=u.due_at,
                objectives_total=len(u.objective_ids),
                objectives_secure=None
                if secure_objectives is None
                else sum(1 for oid in u.objective_ids if oid in secure_objectives),
                notes=u.notes,
            )
            for u in rows
        ]
    return GuardianOverviewOut(
        student_id=student_id,
        student_name=identity.student_display_name(s, student_id),
        scopes=sorted(principal.guardian_scopes.get(student_id, frozenset())),
        summary=summary,
        evaluations_needing_review=evaluation.needs_review_count(s, student_id=student_id)
        if allowed("assessments")
        else None,
        upcoming_assessments=upcoming,
        safety=safety_out,
        suggestions=suggestions(
            wins=summary.recent_wins, focus=summary.focus, upcoming=upcoming or [], timezone=timezone, now=now
        ),
    )


# --- monthly summary (guardian, PHASE-1 W12) -------------------------------------------------------------------

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
INDEPENDENT_HELP_LEVEL = 1  # at most a nudge
SECURED_LIMIT = 10


def month_start(value: str | None, *, today: date) -> date:
    current = today.replace(day=1)
    if value is None:
        return current
    year, month = (int(part) for part in value.split("-"))
    start = date(year, month, 1)
    if start > current:
        raise ApiError(422, "month_not_started", "that month has not started yet")
    return start


def shift_month(start: date, months: int) -> date:
    index = start.year * 12 + start.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def month_window(start: date, timezone: str) -> tuple[datetime, datetime]:
    """UTC bounds [start, end) of a calendar month in the student's timezone."""
    zone = _zone(timezone)
    return (
        datetime.combine(start, time(), zone).astimezone(UTC),
        datetime.combine(shift_month(start, 1), time(), zone).astimezone(UTC),
    )


@dataclass(frozen=True)
class MarkedAnswer:
    subject_id: UUID | None
    awarded: float
    available: float
    settled: bool  # final, or reviewed by a guardian
    help_level: int


def marked_answers(window_events: Sequence[events.EventView]) -> dict[str, MarkedAnswer]:
    """attempt_id -> its latest marks in the window. A guardian's review settles a needs_review evaluation."""
    answers: dict[str, MarkedAnswer] = {}
    for ev in window_events:
        p = ev.payload
        key = str(p.get("attempt_id"))
        if ev.type == "attempt_evaluated":
            answers[key] = MarkedAnswer(
                subject_id=ev.subject_id,
                awarded=float(p["marks_awarded"]),
                available=float(p["marks_available"]),
                settled=p.get("status") == "final",
                help_level=int(p.get("help_level") or 0),
            )
        elif ev.type == "evaluation_overridden" and key in answers:
            answers[key] = replace(
                answers[key],
                awarded=float(p["marks_awarded"]),
                available=float(p["marks_available"]),
                settled=True,
            )
    return answers


def _ratio(part: float, whole: float) -> float | None:
    return round(part / whole, 3) if whole else None


def _study_minutes(window_events: Sequence[events.EventView], subject_id: UUID | None = None) -> int:
    return sum(
        int(ev.payload.get("active_minutes") or 0)
        for ev in window_events
        if ev.type == "session_ended" and (subject_id is None or ev.subject_id == subject_id)
    )


def month_totals(window_events: Sequence[events.EventView], *, timezone: str) -> MonthTotalsOut:
    settled = [a for a in marked_answers(window_events).values() if a.settled]
    return MonthTotalsOut(
        answers_marked=len(marked_answers(window_events)),
        accuracy=_ratio(sum(a.awarded for a in settled), sum(a.available for a in settled)),
        active_days=len({local_date(ev.occurred_at, timezone) for ev in window_events}),
        study_minutes=_study_minutes(window_events),
    )


def month_subject(
    window_events: Sequence[events.EventView], *, subject_id: UUID, subject_name: str, topics_secured: int | None
) -> MonthSubjectOut:
    answers = [a for a in marked_answers(window_events).values() if a.subject_id == subject_id]
    settled = [a for a in answers if a.settled]

    def count(event_type: str) -> int:
        return sum(1 for ev in window_events if ev.type == event_type and ev.subject_id == subject_id)

    awarded, available = sum(a.awarded for a in settled), sum(a.available for a in settled)
    return MonthSubjectOut(
        subject_id=subject_id,
        subject_name=subject_name,
        answers_marked=len(answers),
        marks_awarded=awarded,
        marks_available=available,
        accuracy=_ratio(awarded, available),
        independent_share=_ratio(sum(1 for a in answers if a.help_level <= INDEPENDENT_HELP_LEVEL), len(answers)),
        awaiting_review=len(answers) - len(settled),
        sessions=count("session_ended"),
        study_minutes=_study_minutes(window_events, subject_id),
        mistakes_found=count("mistake_diagnosed"),
        mistakes_resolved=count("mistake_resolved"),
        topics_secured=topics_secured,
    )


def guardian_monthly(
    s: Session, principal: Principal, *, student_id: UUID, month: str | None, now: datetime
) -> MonthlySummaryOut:
    """Month summary for a guardian. Topics "secured" are those last shown at competent or better in the month
    (mastery keeps only the latest demonstration, so a topic shown again later counts in the later month)."""
    require_role(principal, "guardian", "admin")
    require_student_access(principal, student_id, "progress")

    def allowed(scope: str) -> bool:
        return can_access_student(principal, student_id, scope)

    timezone = identity.student_timezone(s, student_id)
    today = local_date(now, timezone)
    start = month_start(month, today=today)
    previous_start, following = shift_month(start, -1), shift_month(start, 1)
    window_start, window_end = month_window(start, timezone)
    previous_window_start, _ = month_window(previous_start, timezone)
    recent = events.list_events(s, student_id=student_id, since=previous_window_start)
    this_month = [ev for ev in recent if window_start <= ev.occurred_at < window_end]
    last_month = [ev for ev in recent if ev.occurred_at < window_start]
    current = start == today.replace(day=1)

    secured: list[WinOut] | None = None
    focus: list[FocusOut] | None = None
    if allowed("mastery"):
        mastery_rows = mastery.list_mastery(s, student_id=student_id)
        shown = [r for r in mastery_rows if r.last_demonstrated_at is not None and r.last_demonstrated_at < window_end]
        secured = recent_wins(shown, since=window_start, limit=len(shown))
        if current:
            open_mistakes = [
                m for m in mistakes.list_mistakes(s, student_id=student_id) if m.status in mistakes.UNRESOLVED
            ]
            focus = focus_items(mastery_rows, open_mistakes)

    subject_ids = sorted({e.subject_id for e in enrollment.list_enrollments(s, [student_id])})
    names = curriculum.subject_summaries(s, subject_ids)
    last_day = min(today, following - timedelta(days=1))
    plans = planner.item_counts(s, student_id=student_id, start=start, end=last_day) if allowed("plans") else None
    return MonthlySummaryOut(
        student_id=student_id,
        student_name=identity.student_display_name(s, student_id),
        month=f"{start:%Y-%m}",
        previous_month=f"{previous_start:%Y-%m}",
        next_month=None if current else f"{following:%Y-%m}",
        days_counted=(last_day - start).days + 1,
        totals=month_totals(this_month, timezone=timezone),
        previous=month_totals(last_month, timezone=timezone),
        subjects=sorted(
            (
                month_subject(
                    this_month,
                    subject_id=sid,
                    subject_name=names[sid].name if sid in names else "",
                    topics_secured=None if secured is None else sum(1 for w in secured if w.subject_id == sid),
                )
                for sid in subject_ids
            ),
            key=lambda m: m.subject_name,
        ),
        plan_items_total=None if plans is None else sum(plans.values()),
        plan_items_completed=None if plans is None else plans.get("completed", 0),
        plan_items_skipped=None if plans is None else plans.get("skipped", 0),
        secured=None if secured is None else secured[:SECURED_LIMIT],
        focus=focus,
    )


# --- suggestions and weekly trends (guardian) ---------------------------------------------------------------------


def suggestions(
    *,
    wins: Sequence[WinOut],
    focus: Sequence[FocusOut],
    upcoming: Sequence[UpcomingBriefOut],
    timezone: str,
    now: datetime,
) -> list[SuggestionOut]:
    """Plain-language next steps for the guardian, from the same stored progress the page shows. No LLM."""
    out: list[SuggestionOut] = []
    if wins:
        win = wins[0]
        out.append(
            SuggestionOut(
                lead="Celebrate",
                text=f"{win.objective_statement} ({win.objective_code}) reached {win.level_name.lower()} this week.",
            )
        )
    mistake = next((f for f in focus if f.kind == "mistake"), None)
    if mistake is not None:
        out.append(
            SuggestionOut(
                lead="Talk it through",
                text=(
                    f"Ask her to explain {mistake.label.lower()} in her own words. Explaining out loud makes it stick."
                ),
            )
        )
    soon = [u for u in upcoming if u.due_at <= now + timedelta(days=SOON_DAYS)]
    if soon:
        next_up = min(soon, key=lambda u: u.due_at)
        day = local_date(next_up.due_at, timezone).strftime("%A")
        ready = (
            ""
            if next_up.objectives_secure is None or not next_up.objectives_total
            else f" {next_up.objectives_secure} of {next_up.objectives_total} topics are secure."
        )
        out.append(
            SuggestionOut(
                lead=f"Before {day}: {next_up.title}",
                text=f"A lighter evening before and an early night help more than extra practice.{ready}",
            )
        )
    if not out:
        out.append(
            SuggestionOut(
                lead="This week",
                text="Nothing stands out yet. A short daily session is the best next step.",
            )
        )
    return out


def week_start_dates(today: date, weeks: int) -> list[date]:
    """Monday of each of the last ``weeks`` weeks, oldest first, the current week last."""
    monday = today - timedelta(days=today.weekday())
    return [monday - timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]


def guardian_trends(s: Session, principal: Principal, *, student_id: UUID, weeks: int, now: datetime) -> TrendsOut:
    """Weekly series behind the guardian charts: topics secure, how answers were reached, study time."""
    require_role(principal, "guardian", "admin")
    require_student_access(principal, student_id, "progress")
    timezone = identity.student_timezone(s, student_id)
    today = local_date(now, timezone)
    starts = week_start_dates(today, weeks)
    zone = _zone(timezone)
    bounds = [datetime.combine(start, time(), zone).astimezone(UTC) for start in starts]
    last_end = datetime.combine(starts[-1] + timedelta(days=WEEK_DAYS), time(), zone).astimezone(UTC)
    ends = [*bounds[1:], last_end]
    history = [ev for ev in events.list_events(s, student_id=student_id, since=bounds[0]) if ev.occurred_at < last_end]
    secure = (
        mastery.secure_counts_at(s, student_id=student_id, moments=[min(end, now) for end in ends])
        if can_access_student(principal, student_id, "mastery")
        else None
    )

    week_rows = []
    for index, start in enumerate(starts):
        in_week = [ev for ev in history if bounds[index] <= ev.occurred_at < ends[index]]
        without_help, with_hints, worked = help_mix(in_week)
        marked = without_help + with_hints + worked
        week_rows.append(
            TrendWeekOut(
                week_start=start,
                topics_secure=None if secure is None else secure[index],
                answers_marked=marked,
                without_help=without_help,
                with_hints=with_hints,
                worked_solution=worked,
                independent_share=_ratio(without_help, marked),
            )
        )

    this_week = [ev for ev in history if ev.occurred_at >= bounds[-1]]
    days = []
    for offset in range(WEEK_DAYS):
        day = starts[-1] + timedelta(days=offset)
        on_day = [ev for ev in this_week if local_date(ev.occurred_at, timezone) == day]
        days.append(TrendDayOut(day=day, study_minutes=_study_minutes(on_day)))

    subject_ids = sorted({e.subject_id for e in enrollment.list_enrollments(s, [student_id])})
    names = curriculum.subject_summaries(s, subject_ids)
    availability = enrollment.availability(s, student_id=student_id)
    return TrendsOut(
        student_id=student_id,
        weeks=week_rows,
        days=days,
        subjects=[
            TrendSubjectOut(
                subject_id=sid,
                subject_name=names[sid].name if sid in names else "",
                study_minutes=_study_minutes(history, sid),
            )
            for sid in subject_ids
        ],
        planned_minutes_per_day=round(sum(availability.values()) / WEEK_DAYS) if availability else 0,
    )


def metacognition(
    s: Session,
    principal: Principal,
    *,
    student_id: UUID,
    subject_id: UUID | None = None,
) -> MetacognitionOut:
    require_student_access(principal, student_id, scope="progress")
    return metacognition_mod.get_metacognitive_profile(s, student_id=student_id, subject_id=subject_id)
