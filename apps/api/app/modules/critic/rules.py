"""Study Critic rule v1 (Phase 2, AC-C1/AC-C2). Pure, deterministic, versioned. No LLM.

It watches *how* she studies, not what she knows — mastery already covers that. Five patterns, each one an
observation with its own window and its own numbers:

    inconsistency        long gaps between study days
    cramming             the week's work bunched into one or two days
    unrealistic_plan     plans she cannot finish, repeatedly
    help_dependency      a rising share of answers needing hints or a worked solution
    subject_imbalance    one enrolled subject getting almost none of the time

Two rules about what a pattern may say, enforced by the wording of the templates in `critic/patterns.yaml`
and by the tests:

1. It describes what happened, with the count and the window. It never diagnoses her — no "she is
   struggling", no "lacks motivation". The reader draws the conclusion.
2. Nothing fires without enough evidence. A quiet fortnight is not a pattern; it is a quiet fortnight.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

RULE_VERSION = "critic_v1"

Severity = Literal["notice", "watch"]
PatternKind = Literal["inconsistency", "cramming", "unrealistic_plan", "help_dependency", "subject_imbalance"]

# Windows and thresholds. Deliberately slack: a critic that fires every week is noise, and noise about a
# child's studying is worse than silence.
WINDOW_DAYS = 28
MIN_ACTIVE_DAYS = 6  # below this there is not enough of a habit to have an opinion about
LONG_GAP_DAYS = 5  # a gap this long or longer counts against consistency
MIN_LONG_GAPS = 2
CRAMMING_SHARE = 0.6  # this much of a week's minutes on a single day
CRAMMING_WEEKS = 2
UNFINISHED_SHARE = 0.5  # plans where this much was left undone
UNFINISHED_WEEKS = 2
MIN_PLAN_ITEMS = 4
HELP_RISE = 0.2  # the helped share rising by this much between halves of the window
MIN_ANSWERS_PER_HALF = 5
IMBALANCE_SHARE = 0.15  # a subject below this share of study minutes
MIN_SUBJECT_MINUTES = 120  # ...once there is at least this much study to divide up


@dataclass(frozen=True)
class DayActivity:
    day: date
    study_minutes: int
    answers: int
    answers_with_help: int
    plan_items: int
    plan_items_done: int


@dataclass(frozen=True)
class SubjectActivity:
    subject_id: str
    subject_name: str
    study_minutes: int


@dataclass(frozen=True)
class Pattern:
    kind: PatternKind
    severity: Severity
    # Numbers the template fills in. Counts and days only — never answer text (ARCHITECTURE §20).
    facts: Mapping[str, str | int | float]
    window_days: int = WINDOW_DAYS
    rule_version: str = RULE_VERSION


def _active(days: Sequence[DayActivity]) -> list[DayActivity]:
    return [d for d in days if d.study_minutes > 0]


def _week_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def inconsistency(days: Sequence[DayActivity]) -> Pattern | None:
    active = sorted(_active(days), key=lambda d: d.day)
    if len(active) < MIN_ACTIVE_DAYS:
        return None
    gaps = [
        (b.day - a.day).days for a, b in zip(active, active[1:], strict=False) if (b.day - a.day).days >= LONG_GAP_DAYS
    ]
    if len(gaps) < MIN_LONG_GAPS:
        return None
    return Pattern(
        kind="inconsistency",
        severity="watch" if len(gaps) >= 3 else "notice",
        facts={"gaps": len(gaps), "longest_gap": max(gaps), "active_days": len(active)},
    )


def cramming(days: Sequence[DayActivity]) -> Pattern | None:
    weeks: dict[date, list[DayActivity]] = {}
    for day in _active(days):
        weeks.setdefault(_week_of(day.day), []).append(day)

    crammed = []
    for week_start, entries in weeks.items():
        total = sum(d.study_minutes for d in entries)
        if total <= 0:
            continue
        biggest = max(d.study_minutes for d in entries)
        if biggest / total >= CRAMMING_SHARE and len(entries) > 1:
            crammed.append((week_start, round(biggest / total, 2)))
    if len(crammed) < CRAMMING_WEEKS:
        return None
    return Pattern(
        kind="cramming",
        severity="watch" if len(crammed) >= 3 else "notice",
        facts={"weeks": len(crammed), "biggest_share": int(max(share for _w, share in crammed) * 100)},
    )


def unrealistic_plan(days: Sequence[DayActivity]) -> Pattern | None:
    weeks: dict[date, tuple[int, int]] = {}
    for day in days:
        planned, done = weeks.get(_week_of(day.day), (0, 0))
        weeks[_week_of(day.day)] = (planned + day.plan_items, done + day.plan_items_done)

    missed = [
        (planned, done)
        for planned, done in weeks.values()
        if planned >= MIN_PLAN_ITEMS and (planned - done) / planned >= UNFINISHED_SHARE
    ]
    if len(missed) < UNFINISHED_WEEKS:
        return None
    planned_total = sum(p for p, _d in missed)
    done_total = sum(d for _p, d in missed)
    return Pattern(
        kind="unrealistic_plan",
        severity="watch" if len(missed) >= 3 else "notice",
        facts={"weeks": len(missed), "planned": planned_total, "finished": done_total},
    )


def help_dependency(days: Sequence[DayActivity]) -> Pattern | None:
    ordered = sorted(days, key=lambda d: d.day)
    half = len(ordered) // 2
    first, second = ordered[:half], ordered[half:]

    def share(window: Sequence[DayActivity]) -> float | None:
        answers = sum(d.answers for d in window)
        if answers < MIN_ANSWERS_PER_HALF:
            return None
        return sum(d.answers_with_help for d in window) / answers

    before, after = share(first), share(second)
    if before is None or after is None or after - before < HELP_RISE:
        return None
    return Pattern(
        kind="help_dependency",
        severity="watch" if after - before >= HELP_RISE * 2 else "notice",
        facts={"before": int(before * 100), "after": int(after * 100)},
    )


def subject_imbalance(subjects: Sequence[SubjectActivity]) -> Pattern | None:
    total = sum(s.study_minutes for s in subjects)
    if len(subjects) < 2 or total < MIN_SUBJECT_MINUTES:
        return None
    quietest = min(subjects, key=lambda s: s.study_minutes)
    share = quietest.study_minutes / total
    if share >= IMBALANCE_SHARE:
        return None
    return Pattern(
        kind="subject_imbalance",
        severity="notice",
        facts={
            "subject": quietest.subject_name,
            "share": int(share * 100),
            "minutes": quietest.study_minutes,
        },
    )


def patterns(days: Sequence[DayActivity], subjects: Sequence[SubjectActivity]) -> list[Pattern]:
    """Every pattern that fires, in a stable order. An empty list is the normal result."""
    found = [
        inconsistency(days),
        cramming(days),
        unrealistic_plan(days),
        help_dependency(days),
        subject_imbalance(subjects),
    ]
    return [p for p in found if p is not None]


def counts(days: Sequence[DayActivity]) -> Counter[str]:
    """Totals for the window, so a surface can say what the patterns were drawn from."""
    return Counter(
        active_days=len(_active(days)),
        study_minutes=sum(d.study_minutes for d in days),
        answers=sum(d.answers for d in days),
        plan_items=sum(d.plan_items for d in days),
        plan_items_done=sum(d.plan_items_done for d in days),
    )
