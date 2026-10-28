"""Three doors into today's work, sized to the time she actually has (docs/GO-LIVE-ENGAGEMENT.md F2).

"I haven't got time to start" is the most common reason a study app stays closed on a weeknight, so today's
work offers three ways in rather than one: a couple of minutes on something that is fading, today's set, or one
topic from the lesson through to its questions.

Pure and deterministic, like the daily set rule. **Every minute figure comes from the content itself** — about
a minute a mark for questions (`learn.pacing`, the examiner's own rule of thumb), and the topic page's own
estimate for the long door, which the service passes in. The sizes below are the budgets the doors aim at; what
she is shown is always the real number, even when it misses the budget, because a door that lies about five
minutes is worse than a door that admits to them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.modules.learn.pacing import question_minutes

QUICK_MINUTES = 3  # the budget the short door aims at
DEEP_MINUTES = 25  # what the long door is sized for; the topic's own estimate is what gets shown
MAX_DEEP_LOOKUPS = 3  # how many of today's topics to ask about before the long door gives up (each is a page read)


@dataclass(frozen=True)
class Item:
    """One question in today's set, as the doors need to see it."""

    item_id: UUID
    objective_id: UUID
    marks: int
    reason_code: str
    to_do: bool


def minutes_for(items: Sequence[Item]) -> int:
    return sum(question_minutes(item.marks) for item in items)


def quick_pick(items: Sequence[Item], *, budget: int = QUICK_MINUTES) -> list[Item]:
    """Her shortest unanswered questions on topics due for revision, inside the budget.

    Shortest first, so the door holds as many as it honestly can. One question is always offered even when it
    alone runs over the budget — the door then shows that question's real minutes instead of the budget.
    """
    due = [item for item in items if item.to_do and item.reason_code.startswith("retention")]
    picked: list[Item] = []
    spent = 0
    for item in sorted(due, key=lambda i: (i.marks, str(i.item_id))):
        cost = question_minutes(item.marks)
        if picked and spent + cost > budget:
            break
        picked.append(item)
        spent += cost
        if spent >= budget:
            break
    return picked


def to_do(items: Sequence[Item]) -> list[Item]:
    return [item for item in items if item.to_do]


def deep_candidates(items: Sequence[Item]) -> list[UUID]:
    """The topics the long door may open, in the rule's order of claim: those today's set still has work on.

    Only candidates, because whether a topic has anything left to read or try is a question for her record, not
    for this rule. The caller walks them in order and takes the first with minutes on it — the first candidate
    can be a topic she has already read and practised, which was what the door offered before (25 Oct 2026).
    """
    out: list[UUID] = []
    for item in items:
        if item.to_do and item.objective_id not in out:
            out.append(item.objective_id)
    return out
