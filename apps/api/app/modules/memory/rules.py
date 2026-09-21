"""Learning memory validation (ARCHITECTURE §15), pure: the LLM proposes, these rules decide.

- every statement must cite at least one event from the session digest (AC-M3); unknown references are dropped
- a statement similar to an active one of the same kind merges its evidence into it instead of duplicating
- a strength contradicting an active difficulty/misconception on the same objective (or vice versa) supersedes it
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

KINDS = ("strength", "difficulty", "misconception", "preference", "note")
OPPOSITES = {"strength": ("difficulty", "misconception"), "difficulty": ("strength",), "misconception": ("strength",)}
MAX_STATEMENTS = 5
MAX_STATEMENT_CHARS = 240
SIMILARITY = 0.6
_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class DigestEvent:
    ref: str  # short reference shown to the model, e.g. "E3"
    event_id: UUID
    objective_ids: frozenset[UUID]


@dataclass(frozen=True)
class Existing:
    id: UUID
    kind: str
    statement: str
    evidence: frozenset[UUID]
    objective_ids: frozenset[UUID]


@dataclass(frozen=True)
class Proposal:
    kind: str
    statement: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class NewStatement:
    kind: str
    statement: str
    event_ids: tuple[UUID, ...]
    objective_ids: frozenset[UUID]
    supersedes: tuple[UUID, ...]


@dataclass(frozen=True)
class Merge:
    existing_id: UUID
    add_event_ids: tuple[UUID, ...]


@dataclass
class Decision:
    new: list[NewStatement] = field(default_factory=list)
    merges: list[Merge] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # reason codes only (no text)


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2}


def similar(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return a.strip().lower() == b.strip().lower()
    return len(wa & wb) / len(wa | wb) >= SIMILARITY


def decide(proposals: Sequence[Proposal], digest: dict[str, DigestEvent], existing: Sequence[Existing]) -> Decision:
    decision = Decision()
    for proposal in proposals[:MAX_STATEMENTS]:
        statement = " ".join(proposal.statement.split())
        if proposal.kind not in KINDS:
            decision.rejected.append("unknown_kind")
            continue
        if not statement or len(statement) > MAX_STATEMENT_CHARS:
            decision.rejected.append("bad_statement")
            continue
        cited = list(dict.fromkeys(digest[r] for r in proposal.evidence_refs if r in digest))
        if not cited:
            decision.rejected.append("no_evidence")  # AC-M3
            continue
        event_ids = tuple(e.event_id for e in cited)
        objectives = frozenset(o for e in cited for o in e.objective_ids)

        duplicate = next((e for e in existing if e.kind == proposal.kind and similar(e.statement, statement)), None)
        if duplicate is not None:
            added = tuple(i for i in event_ids if i not in duplicate.evidence)
            if added:
                decision.merges.append(Merge(duplicate.id, added))
            else:
                decision.rejected.append("duplicate")
            continue
        if any(n.kind == proposal.kind and similar(n.statement, statement) for n in decision.new):
            decision.rejected.append("duplicate")
            continue
        supersedes = tuple(
            e.id
            for e in existing
            if e.kind in OPPOSITES.get(proposal.kind, ()) and objectives and e.objective_ids & objectives
        )
        decision.new.append(NewStatement(proposal.kind, statement, event_ids, objectives, supersedes))
    return decision
