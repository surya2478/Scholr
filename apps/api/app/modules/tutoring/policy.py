"""Help-ladder policy (ARCHITECTURE §10). Pure and deterministic.

The LLM writes hints and explanations; this module decides *how much* help is allowed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Literal


class HelpLevel(IntEnum):
    NONE = 0
    NUDGE = 1
    HINT = 2
    WORKED_EXAMPLE = 3
    NEXT_STEP = 4
    FULL_SOLUTION = 5


ASSISTANCE_MULTIPLIER: dict[HelpLevel, float] = {
    HelpLevel.NONE: 1.0,
    HelpLevel.NUDGE: 0.9,
    HelpLevel.HINT: 0.7,
    HelpLevel.WORKED_EXAMPLE: 0.5,
    HelpLevel.NEXT_STEP: 0.3,
    HelpLevel.FULL_SOLUTION: 0.1,
}

Band = Literal["developing", "competent", "mastered"]

# Help level after the 1st, 2nd, 3rd and 4th+ incorrect attempt, per mastery band.
ESCALATION: dict[Band, tuple[HelpLevel, HelpLevel, HelpLevel, HelpLevel]] = {
    "developing": (HelpLevel.HINT, HelpLevel.WORKED_EXAMPLE, HelpLevel.NEXT_STEP, HelpLevel.FULL_SOLUTION),
    "competent": (HelpLevel.NUDGE, HelpLevel.HINT, HelpLevel.WORKED_EXAMPLE, HelpLevel.FULL_SOLUTION),
    "mastered": (HelpLevel.NUDGE, HelpLevel.NUDGE, HelpLevel.HINT, HelpLevel.NEXT_STEP),
}


def band_for(mastery_level: int) -> Band:
    if mastery_level <= 2:
        return "developing"
    if mastery_level == 3:
        return "competent"
    return "mastered"


def help_after_miss(
    *, mastery_level: int, miss_number: int, current_max: HelpLevel, frustrated: bool = False
) -> HelpLevel:
    """Help level to offer after the Nth incorrect or partial attempt on one item."""
    if miss_number < 1:
        raise ValueError("miss_number starts at 1")
    table = ESCALATION[band_for(mastery_level)]
    idx = min(miss_number, len(table)) - 1
    if frustrated:
        idx = min(idx + 1, len(table) - 1)
    return max(table[idx], current_max)


HelpAction = Literal["ask_for_attempt", "give_help"]


@dataclass(frozen=True)
class HelpDecision:
    action: HelpAction
    level: HelpLevel


def respond_to_help_request(
    *, attempts_made: int, asks_without_attempt: int, current_max: HelpLevel, frustrated: bool = False
) -> HelpDecision:
    """An explicit request for help.

    With no attempt yet, ask once for an attempt or first step; never refuse more than once.
    """
    if attempts_made == 0 and asks_without_attempt == 0 and not frustrated:
        return HelpDecision("ask_for_attempt", current_max)
    step = 2 if frustrated else 1
    level = HelpLevel(min(int(current_max) + step, int(HelpLevel.FULL_SOLUTION)))
    return HelpDecision("give_help", max(level, HelpLevel.NUDGE))


def requires_isomorphic_followup(max_help: HelpLevel) -> bool:
    """After a full solution, progress is credited only after a similar item is attempted."""
    return max_help >= HelpLevel.FULL_SOLUTION


def should_request_self_explanation(consecutive_correct: int, every_n: int) -> bool:
    return every_n > 0 and consecutive_correct > 0 and consecutive_correct % every_n == 0


def is_frustrated(
    help_request_times: Sequence[datetime],
    *,
    now: datetime,
    window: timedelta = timedelta(minutes=5),
    threshold: int = 3,
    classifier_flag: bool = False,
) -> bool:
    recent = [t for t in help_request_times if now - window <= t <= now]
    return classifier_flag or len(recent) >= threshold
