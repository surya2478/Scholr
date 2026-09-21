"""The daily practice set: a handful of short questions for today, chosen by rule (docs/STUDENT-APP.md step 4).

Pure and deterministic, like the planner engine. The service gathers the inputs; this decides.

What she is asked, in this order of claim:
1. the objectives on today's plan, in plan order;
2. objectives with an open mistake, worst first;
3. objectives at retention risk, high before medium;
4. objectives she has only read the lesson for (Introduced), so reading is followed by trying.

One question per objective first, then a second for the earliest ones if the set is still short. A question she
answered in the last ``RECENT_DAYS`` days is not set again; short questions (``SHORT_MARKS`` or fewer) come first;
ties break on a hash of the day and the question, so the set is stable for a day and varies across days.
Excluded objectives (validation-study control topics, AC-P2) are never used.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

RULE_VERSION = "daily_set_v1"
SET_SIZE = 6
RECENT_DAYS = 14
SHORT_MARKS = 4


@dataclass(frozen=True)
class Want:
    objective_id: UUID
    reason_code: str


@dataclass(frozen=True)
class Candidate:
    item_id: UUID
    marks: int


@dataclass(frozen=True)
class Pick:
    item_id: UUID
    objective_id: UUID
    reason_code: str


def _order(candidates: Sequence[Candidate], seed: str) -> list[Candidate]:
    def key(c: Candidate) -> tuple[bool, str]:
        return c.marks > SHORT_MARKS, hashlib.sha256(f"{seed}:{c.item_id}".encode()).hexdigest()

    return sorted(candidates, key=key)


def choose(
    wants: Sequence[Want],
    items: Mapping[UUID, Sequence[Candidate]],
    *,
    recent: Collection[UUID],
    excluded: Collection[UUID],
    seed: str,
    size: int = SET_SIZE,
) -> list[Pick]:
    ordered: list[Want] = []
    seen: set[UUID] = set()
    for want in wants:  # the first reason an objective is wanted for is the one she is shown
        if want.objective_id in seen or want.objective_id in excluded:
            continue
        seen.add(want.objective_id)
        ordered.append(want)

    picks: list[Pick] = []
    used: set[UUID] = set()
    for _ in range(2):
        for want in ordered:
            if len(picks) >= size:
                return picks
            pool = [c for c in items.get(want.objective_id, ()) if c.item_id not in recent and c.item_id not in used]
            if not pool:
                continue
            chosen = _order(pool, seed)[0]
            used.add(chosen.item_id)
            picks.append(Pick(chosen.item_id, want.objective_id, want.reason_code))
    return picks
