"""Planner v1 (ARCHITECTURE §16). Pure: a day's inputs in, a plan draft out.

capacity = availability - commitments - 15% buffer (x0.6 on the week's lighter day)
priority = 3*assessment_within_14d + 2*retention_high + 2*open_mistake_high + 2*current_school_topic
         + 1*low_mastery + 0.5*challenge + exam_weight(subject)
exam_weight = 1.5 * urgency * (0.5 + 0.5*unseen), urgency = 1 - days_to_exam/730 (0 beyond two years), unseen =
      share of the syllabus not yet introduced. The nearer exam and the less-covered syllabus pull harder, but never
      past a high-severity mistake or the current school topic (each worth 2).
fill: core (assessment prep, mistake fixes, revision, school topic) first, then reinforcement of an external
      class, then practice, then challenge; at most one reinforcement item a day (AC-X9);
      new learning (a current school topic with no evidence yet) capped at 40% of capacity; assessment prep is
      never capped; no block longer than 45 minutes.
overload: when core exceeds capacity, optional items are dropped and the plan says why. Dropped core items are not
      carried explicitly: their signals persist, so the next days' plans pick them up again.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
from typing import Literal
from uuid import UUID

from app.tools.dates import RecurrenceError, occurs_on

GENERATOR_VERSION = "planner_v1"
BUFFER = 0.15
LIGHTER_DAY_FACTOR = 0.6
NEW_LEARNING_CAP = 0.40
MAX_BLOCK_MINUTES = 45
ASSESSMENT_WINDOW_DAYS = 14
EXAM_HORIZON_DAYS = 730  # two years out, an exam adds nothing to a day's choices
EXAM_WEIGHT_MAX = 1.5

Kind = Literal["assessment", "mistake_fix", "revision", "school_topic", "reinforcement", "practice", "challenge"]
EST_MINUTES: dict[str, int] = {
    "assessment": 30,
    "reinforcement": 20,
    "mistake_fix": 15,
    "revision": 20,
    "school_topic": 25,
    "practice": 20,
    "challenge": 15,
}
CORE_KINDS = ("assessment", "mistake_fix", "revision", "school_topic")
OPTIONAL_KINDS = ("reinforcement", "practice", "challenge")
# Phase 3, "complement never duplicate": the external programme may claim at most this much of a day (AC-X9).
MAX_REINFORCEMENT_ITEMS = 1
# Small enough that the trace's own order only decides between otherwise equal candidates.
EXTERNAL_RANK_STEP = 0.1
_KIND_ORDER = {kind: i for i, kind in enumerate((*CORE_KINDS, *OPTIONAL_KINDS))}


@dataclass(frozen=True)
class CommitmentIn:
    title: str
    rrule: str
    duration_min: int


@dataclass(frozen=True)
class Capacity:
    available: int
    commitments: int
    buffer: int
    lighter_day: bool
    minutes: int
    unsupported_rules: tuple[str, ...] = ()


def day_capacity(day: date, availability: Mapping[int, int], commitments: Sequence[CommitmentIn]) -> Capacity:
    available = availability.get(day.weekday(), 0)
    committed = 0
    unsupported: list[str] = []
    for commitment in commitments:
        try:
            if occurs_on(commitment.rrule, day):
                committed += commitment.duration_min
        except RecurrenceError:
            unsupported.append(commitment.title)
    lighter = bool(availability) and day.weekday() == min(availability, key=lambda wd: (availability[wd], wd))
    base = max(0, available - committed)
    buffer = math.ceil(base * BUFFER)
    minutes = base - buffer
    if lighter:
        minutes = int(minutes * LIGHTER_DAY_FACTOR)
    return Capacity(available, committed, buffer, lighter, minutes, tuple(unsupported))


@dataclass(frozen=True)
class ObjectiveSignal:
    objective_id: UUID
    subject_id: UUID
    assessment_due: bool = False  # an upcoming assessment within 14 days covers it
    retention_risk: str = "none"  # none | medium | high
    mistake_severity: str | None = None  # worst unresolved mistake pattern
    school_topic: bool = False  # in the current school teaching plan
    mastery_level: int | None = None  # None: no evidence yet
    # A recent class the student learns elsewhere leans on this objective (external_training.trace).
    # `external_rank` is that trace's own order, 0 = its best suggestion, so the day picks up the strongest.
    external_weakness: bool = False
    external_rank: int | None = None
    exam_weight: float = 0.0  # the subject's pull from its exam date and unseen syllabus (exam_weight())


@dataclass(frozen=True)
class PlanEntry:
    objective_id: UUID
    subject_id: UUID
    kind: str
    est_minutes: int
    priority: float
    reason_code: str
    new_learning: bool


def exam_weight(days_to_exam: int | None, unseen_share: float) -> float:
    """How hard a subject's exam pulls on today's choices: nearer exam, and more of the syllabus unseen, pull harder.

    Sociology in November 2026 (exam June 2027, 214 days, 86% unseen) weighs about 1.0; Maths (June 2028, 580 days)
    about 0.3. Without this, a mock that had passed left Sociology with nothing to say for it, and equal priorities
    were settled by the order of internal ids.
    """
    if days_to_exam is None or days_to_exam < 0:
        return 0.0
    urgency = max(0.0, 1 - days_to_exam / EXAM_HORIZON_DAYS)
    unseen = min(1.0, max(0.0, unseen_share))
    return round(EXAM_WEIGHT_MAX * urgency * (0.5 + 0.5 * unseen), 3)


def priority(signal: ObjectiveSignal) -> float:
    level = signal.mastery_level
    low_mastery = level is None or level <= 2
    challenge = level is not None and level >= 4 and signal.retention_risk == "none"
    return (
        3 * signal.assessment_due
        + 2 * (signal.retention_risk == "high")
        + 2 * (signal.mistake_severity == "high")
        + 2 * signal.school_topic
        + 1.5 * signal.external_weakness
        - EXTERNAL_RANK_STEP * (signal.external_rank or 0)
        + 1 * low_mastery
        + 0.5 * challenge
        + signal.exam_weight
    )


def entry_for(signal: ObjectiveSignal) -> PlanEntry | None:
    level = signal.mastery_level
    if signal.assessment_due:
        kind, reason = "assessment", "assessment_soon"
    elif signal.mistake_severity in ("high", "medium"):
        kind, reason = "mistake_fix", f"open_mistake_{signal.mistake_severity}"
    elif signal.retention_risk in ("high", "medium"):
        kind, reason = "revision", f"retention_{signal.retention_risk}"
    elif signal.school_topic:
        new = level is None or level == 0
        kind, reason = "school_topic", "new_school_topic" if new else "current_school_topic"
    elif signal.external_weakness:
        kind, reason = "reinforcement", "external_class_gap"
    elif level is not None and level <= 2:
        kind, reason = "practice", "low_mastery"
    elif level is not None and level >= 4:
        kind, reason = "challenge", "ready_for_challenge"
    else:
        return None
    return PlanEntry(
        objective_id=signal.objective_id,
        subject_id=signal.subject_id,
        kind=kind,
        est_minutes=min(EST_MINUTES[kind], MAX_BLOCK_MINUTES),
        priority=priority(signal),
        reason_code=reason,
        new_learning=reason == "new_school_topic",
    )


@dataclass(frozen=True)
class PlanDraft:
    entries: list[PlanEntry]
    dropped: list[PlanEntry]
    capacity: int
    overload: bool
    excluded_control: int


def build_plan(
    signals: Sequence[ObjectiveSignal], *, capacity_minutes: int, control_objectives: set[UUID]
) -> PlanDraft:
    """AC-P1: never exceeds capacity. AC-P2: validation-study control objectives never appear."""
    excluded = sum(1 for s in signals if s.objective_id in control_objectives)
    candidates = [e for s in signals if s.objective_id not in control_objectives and (e := entry_for(s)) is not None]
    candidates.sort(key=lambda e: (-e.priority, _KIND_ORDER[e.kind], str(e.objective_id)))
    core = [e for e in candidates if e.kind in CORE_KINDS]
    optional = [e for e in candidates if e.kind in OPTIONAL_KINDS]
    overload = sum(e.est_minutes for e in core) > capacity_minutes

    planned: list[PlanEntry] = []
    dropped: list[PlanEntry] = []
    used = new_used = reinforcement_used = 0
    for entry in [*core, *optional]:
        if entry.kind in OPTIONAL_KINDS and overload:
            dropped.append(entry)
            continue
        if entry.kind == "reinforcement" and reinforcement_used >= MAX_REINFORCEMENT_ITEMS:
            dropped.append(entry)
            continue
        if entry.new_learning and new_used + entry.est_minutes > NEW_LEARNING_CAP * capacity_minutes:
            dropped.append(entry)
            continue
        if used + entry.est_minutes > capacity_minutes:
            dropped.append(entry)
            continue
        planned.append(entry)
        used += entry.est_minutes
        new_used += entry.est_minutes if entry.new_learning else 0
        reinforcement_used += entry.kind == "reinforcement"
    return PlanDraft(planned, dropped, capacity_minutes, overload, excluded)


def notice_codes(*, overload: bool, lighter_day: bool, capacity_minutes: int) -> list[str]:
    """What the plan says about the shape of the day, in the order it should be read.

    A day with no capacity says only that. "Today is full, so optional practice was left out" is about a day full
    of study, and on a day with no study time in it nothing was left out *because the day was full* — the core
    work simply had nowhere to go. Said together the two read as nonsense, which is what her plan did on Monday
    26 Oct 2026: one IIT class in the evening, no study window, and both notices at once.
    """
    if capacity_minutes <= 0:
        return ["no_capacity"]
    codes = []
    if overload:
        codes.append("overload")
    if lighter_day:
        codes.append("lighter_day")
    return codes


# --- day timeline ------------------------------------------------------------------------------------------------

# Where study blocks may be placed around fixed commitments. Starting assumption (CONTEXT U13: school in the day,
# IIT classes in the evening); move it to the household seed once the family confirms their study hours.
WEEKDAY_WINDOW = (time(16, 0), time(21, 0))
WEEKEND_WINDOW = (time(9, 0), time(19, 0))
BLOCK_GAP_MINUTES = 5
LAST_MINUTE_OF_DAY = 24 * 60 - 1


@dataclass(frozen=True)
class FixedBlock:
    """A commitment on this day. Fixed: the planner works around it, never over it."""

    title: str
    detail: str | None
    start: time
    minutes: int


@dataclass(frozen=True)
class TimelineBlock:
    kind: str  # "commitment", or the plan item's kind
    title: str
    detail: str | None
    minutes: int
    start: time | None  # None: it did not fit today's window, so it has no set time
    end: time | None
    item_index: int | None  # position in the plan's item list; None for commitments


def _to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _to_time(value: int) -> time:
    return time(min(value, LAST_MINUTE_OF_DAY) // 60, min(value, LAST_MINUTE_OF_DAY) % 60)


def schedule_day(
    items: Sequence[tuple[str, str, str | None, int]],
    fixed: Sequence[FixedBlock],
    *,
    weekend: bool,
    window: tuple[time, time] | None = None,
) -> list[TimelineBlock]:
    """Lay out the day: commitments at their own times, plan items in the gaps between them, in plan order.

    ``items`` are (kind, title, detail, minutes) in plan order. An item that does not fit keeps its place in the
    list without a time, so the student still sees it.
    """
    start_at, end_at = window or (WEEKEND_WINDOW if weekend else WEEKDAY_WINDOW)
    day_end = _to_minutes(end_at)
    busy = sorted(((_to_minutes(f.start), _to_minutes(f.start) + f.minutes, f) for f in fixed), key=lambda b: b[0])
    gaps: list[list[int]] = []
    cursor = _to_minutes(start_at)
    for begins, ends, _ in busy:
        if begins - BLOCK_GAP_MINUTES > cursor:  # leave the same gap before a commitment as after one
            gaps.append([cursor, min(begins - BLOCK_GAP_MINUTES, day_end)])
        cursor = max(cursor, ends + BLOCK_GAP_MINUTES)
    gaps.append([cursor, day_end])
    gaps = [gap for gap in gaps if gap[1] > gap[0]]

    blocks = [
        TimelineBlock("commitment", f.title, f.detail, f.minutes, f.start, _to_time(ends), None) for _, ends, f in busy
    ]
    earliest = 0  # plan order is priority order: an item never starts before the one above it ends
    for index, (kind, title, detail, minutes) in enumerate(items):
        placed = next(((gap, max(gap[0], earliest)) for gap in gaps if gap[1] - max(gap[0], earliest) >= minutes), None)
        if placed is None:
            blocks.append(TimelineBlock(kind, title, detail, minutes, None, None, index))
            continue
        slot, begins = placed
        slot[0] = earliest = begins + minutes + BLOCK_GAP_MINUTES
        blocks.append(TimelineBlock(kind, title, detail, minutes, _to_time(begins), _to_time(begins + minutes), index))
    return sorted(blocks, key=lambda b: (b.start is None, _to_minutes(b.start) if b.start else 0))
