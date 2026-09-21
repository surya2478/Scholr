"""Learning engine (ARCHITECTURE §10): session state, help decisions, item selection and reply guards.

Pure functions only — no database, no LLM. The tutoring service loads inputs, calls these, and persists results.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.modules.tutoring.policy import (
    HelpDecision,
    HelpLevel,
    help_after_miss,
    is_frustrated,
    requires_isomorphic_followup,
    respond_to_help_request,
)

Phase = Literal["select_task", "await_attempt", "ended"]
NO_HELP_MODES = frozenset({"test"})
HELP_LEVEL_NAMES = {
    HelpLevel.NONE: "no help",
    HelpLevel.NUDGE: "nudge",
    HelpLevel.HINT: "hint",
    HelpLevel.WORKED_EXAMPLE: "worked example of a similar problem",
    HelpLevel.NEXT_STEP: "next step only",
    HelpLevel.FULL_SOLUTION: "full solution",
}
MAX_HELP_TIMESTAMPS = 20


@dataclass(frozen=True)
class SessionState:
    """Stored in learning_session.state. Attempts and marks are not duplicated here: they are read from events."""

    phase: Phase = "select_task"
    item_id: str | None = None
    help_level: int = 0
    asks_without_attempt: int = 0
    help_requests: tuple[str, ...] = ()  # ISO timestamps of explicit help requests, oldest first
    needs_isomorphic: bool = False  # after a full solution, the next item must practise the same objective
    isomorphic_objective_ids: tuple[str, ...] = ()
    # Items already put in front of her this session. Recency alone is not enough: it only knows about
    # answers that were submitted, so asking for the next question twice used to hand back the same one.
    served_item_ids: tuple[str, ...] = ()

    @classmethod
    def load(cls, data: Mapping[str, Any] | None) -> SessionState:
        data = data or {}
        return cls(
            phase=data.get("phase", "select_task"),
            item_id=data.get("item_id"),
            help_level=int(data.get("help_level", 0)),
            asks_without_attempt=int(data.get("asks_without_attempt", 0)),
            help_requests=tuple(data.get("help_requests", ())),
            needs_isomorphic=bool(data.get("needs_isomorphic", False)),
            isomorphic_objective_ids=tuple(data.get("isomorphic_objective_ids", ())),
            served_item_ids=tuple(data.get("served_item_ids", ())),
        )

    def dump(self) -> dict[str, Any]:
        data = asdict(self)
        data["help_requests"] = list(self.help_requests)
        data["isomorphic_objective_ids"] = list(self.isomorphic_objective_ids)
        data["served_item_ids"] = list(self.served_item_ids)
        return data


# How many of this session's items to remember, so a long session can still come back to an early one.
SERVED_MEMORY = 20


def start_item(state: SessionState, item_id: UUID, objective_ids: Sequence[UUID]) -> SessionState:
    """Present a new item. Practising the objective of a fully-solved item clears the isomorphic requirement."""
    clears = state.needs_isomorphic and bool(set(state.isomorphic_objective_ids) & {str(o) for o in objective_ids})
    return replace(
        state,
        phase="await_attempt",
        item_id=str(item_id),
        help_level=0,
        asks_without_attempt=0,
        needs_isomorphic=state.needs_isomorphic and not clears,
        isomorphic_objective_ids=() if clears else state.isomorphic_objective_ids,
        served_item_ids=(*state.served_item_ids, str(item_id))[-SERVED_MEMORY:],
    )


@dataclass(frozen=True)
class ItemProgress:
    attempts: int  # attempts on the current item in this session
    misses: int  # evaluated attempts that lost marks


def decide_help(state: SessionState, *, progress: ItemProgress, mastery_level: int, now: datetime) -> HelpDecision:
    """Explicit help request (AC-L1, AC-L2): ask for an attempt once, then escalate per the policy tables."""
    frustrated = is_frustrated([*(datetime.fromisoformat(t) for t in state.help_requests), now], now=now)
    current = HelpLevel(state.help_level)
    decision = respond_to_help_request(
        attempts_made=progress.attempts,
        asks_without_attempt=state.asks_without_attempt,
        current_max=current,
        frustrated=frustrated,
    )
    if decision.action == "give_help" and progress.misses:
        floor = help_after_miss(
            mastery_level=mastery_level, miss_number=progress.misses, current_max=current, frustrated=frustrated
        )
        return HelpDecision("give_help", max(decision.level, floor))
    return decision


def after_help(
    state: SessionState, decision: HelpDecision, now: datetime, objective_ids: Sequence[UUID] = ()
) -> SessionState:
    requests = (*state.help_requests, now.isoformat())[-MAX_HELP_TIMESTAMPS:]
    if decision.action == "ask_for_attempt":
        return replace(state, asks_without_attempt=state.asks_without_attempt + 1, help_requests=requests)
    full = requires_isomorphic_followup(decision.level)
    return replace(
        state,
        help_level=max(state.help_level, int(decision.level)),
        help_requests=requests,
        needs_isomorphic=state.needs_isomorphic or full,
        isomorphic_objective_ids=tuple(str(o) for o in objective_ids) if full else state.isomorphic_objective_ids,
    )


# ---------------------------------------------------------------------------
# Item selection (ARCHITECTURE §11, deterministic)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemCandidate:
    id: UUID
    objective_ids: tuple[UUID, ...]
    marks: int
    source_ref: str | None


def choose_item(
    candidates: Sequence[ItemCandidate],
    *,
    mastery_levels: Mapping[UUID, int],
    mistake_objectives: set[UUID],
    recent_item_ids: set[UUID],
    required_objectives: set[UUID] = frozenset(),  # type: ignore[assignment]
    preferred_objectives: set[UUID] = frozenset(),  # type: ignore[assignment]
) -> ItemCandidate | None:
    """Pick the next practice item: required objectives first (isomorphic follow-up), then session objective,
    then open mistakes and low mastery. Items attempted recently are avoided while alternatives exist."""
    pool = [c for c in candidates if c.id not in recent_item_ids] or list(candidates)
    for wanted in (required_objectives, preferred_objectives):
        if wanted:
            narrowed = [c for c in pool if wanted & set(c.objective_ids)]
            if narrowed:
                pool = narrowed
                break
            if wanted is required_objectives:
                return None  # the follow-up must practise the same objective; nothing suitable is available

    def priority(c: ItemCandidate) -> int:
        objectives = set(c.objective_ids)
        level = min((mastery_levels.get(o, 0) for o in objectives), default=0)
        return (3 if objectives & mistake_objectives else 0) + max(0, 3 - level)

    return min(pool, key=lambda c: (-priority(c), c.marks, c.source_ref or ""), default=None)


# ---------------------------------------------------------------------------
# Reply guards
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.lstrip("-") for n in _NUMBER.findall(text.replace("−", "-").replace(",", ""))}


def leaks_answer(message: str, answer_spec: Mapping[str, Any], *, help_level: int, question_text: str) -> bool:
    """Below a full solution, the reply must not contain the final answer (numbers from the mark-scheme answer that
    are not already given in the question)."""
    if help_level >= HelpLevel.FULL_SOLUTION:
        return False
    answer = str(answer_spec.get("answer") or "")
    secret = {n for n in _numbers(answer) - _numbers(question_text) if len(n.replace(".", "")) >= 2}
    return bool(secret & _numbers(message))


GroundingState = Literal["HIGH", "MEDIUM", "LOW", "NONE"]


@dataclass(frozen=True)
class GroundingPlan:
    answer_allowed: bool  # False: reply with the "not enough material" template, no LLM call
    prefix: str | None
    suffix: str | None


GENERAL_LABEL = "General explanation (not from your course materials): "
LIMITED_NOTE = "Based on limited material — check this in your textbook."


UNGROUNDED_STATES = frozenset({"LOW", "NONE"})


def usable_citations(citations: list[int], *, state: str, excerpts: int) -> list[int]:
    """Excerpt numbers a reply may show as sources. LOW/NONE replies are labelled as general explanations, so they
    cite nothing even when the model lists weakly related excerpts; out-of-range and repeated numbers are dropped."""
    if state in UNGROUNDED_STATES:
        return []
    return [i for i in dict.fromkeys(citations) if 0 < i <= excerpts]


def grounding_plan(state: GroundingState, *, citation_critical: bool) -> GroundingPlan:
    """ARCHITECTURE §9.5. Subjects whose config requires citations (e.g. named studies) do not answer on NONE."""
    if state == "HIGH":
        return GroundingPlan(True, None, None)
    if state == "MEDIUM":
        return GroundingPlan(True, None, LIMITED_NOTE)
    if state == "LOW" or not citation_critical:
        return GroundingPlan(True, GENERAL_LABEL, None)
    return GroundingPlan(False, None, None)
