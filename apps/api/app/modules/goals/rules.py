"""Goal measures (Phase 2, AC-G1). Pure, deterministic, versioned. No LLM.

A goal Scholr will track has to be something Scholr can *count*. "Work harder" is not a goal; "eight topics
secure in Sociology by March" is. Every measure here is derived from evidence the app already holds, so a
goal can never be marked achieved by anyone simply saying it was.

Direction matters: most measures climb towards the target, but open mistakes fall towards it, and progress
has to read correctly either way.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

RULE_VERSION = "goals_v1"

Measure = Literal["topics_secure", "active_days_per_week", "answers_without_help", "open_mistakes"]
Direction = Literal["rise", "fall"]

# What each measure counts, how it moves, and how it is written. Data rather than branching, so adding a
# measure later is one entry plus the reading that fills it.
MEASURES: dict[Measure, dict[str, object]] = {
    "topics_secure": {
        "direction": "rise",
        "unit": "topics",
        "label": "Topics secure",
        "needs_subject": True,
        "help": "Objectives at competent or better.",
    },
    "active_days_per_week": {
        "direction": "rise",
        "unit": "days a week",
        "label": "Days studied each week",
        "needs_subject": False,
        "help": "Averaged over the last four weeks.",
    },
    "answers_without_help": {
        "direction": "rise",
        "unit": "%",
        "label": "Answers solved without help",
        "needs_subject": False,
        "help": "Share of marked answers needing no hint or worked solution.",
    },
    "open_mistakes": {
        "direction": "fall",
        "unit": "open mistakes",
        "label": "Mistakes still open",
        "needs_subject": False,
        "help": "Mistake patterns not yet resolved.",
    },
}


@dataclass(frozen=True)
class Progress:
    current: float
    target: float
    direction: Direction
    # 0..1 towards the target from where she started, or None when there is no baseline to measure from.
    share: float | None
    reached: bool
    days_left: int | None


def measure_config(measure: str) -> Mapping[str, object]:
    if measure not in MEASURES:
        raise KeyError(measure)
    return MEASURES[measure]  # type: ignore[index]


def progress(
    *,
    measure: Measure,
    current: float,
    target: float,
    baseline: float | None,
    target_date: date | None,
    today: date,
) -> Progress:
    direction: Direction = MEASURES[measure]["direction"]  # type: ignore[assignment]
    reached = current >= target if direction == "rise" else current <= target

    share: float | None = None
    if baseline is not None:
        span = target - baseline if direction == "rise" else baseline - target
        moved = current - baseline if direction == "rise" else baseline - current
        if span > 0:
            share = round(max(0.0, min(1.0, moved / span)), 4)
        elif reached:
            share = 1.0

    return Progress(
        current=round(current, 4),
        target=round(target, 4),
        direction=direction,
        share=share,
        reached=reached,
        days_left=(target_date - today).days if target_date else None,
    )


def is_realistic(*, measure: Measure, target: float, current: float) -> bool:
    """A goal has to ask for a change, in the direction the measure actually moves.

    Refusing an impossible or already-met target at the point it is set is kinder than letting her watch a
    bar that can never move.
    """
    direction = MEASURES[measure]["direction"]
    if measure == "answers_without_help" and not 0 <= target <= 100:
        return False
    if target < 0:
        return False
    return target > current if direction == "rise" else target < current
