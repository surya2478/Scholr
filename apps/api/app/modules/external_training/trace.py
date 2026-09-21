"""Tracing an external-class weakness down to the IGCSE work that would fix it (AC-X5..X8).

Pure and deterministic — no database, no LLM. The rule Phase 3 is built around is *complement, never
duplicate*: the answer is never "revise the IIT lesson again", it is always an objective in a subject Scholr
teaches, chosen because the foundation under that lesson is weak.

The walk:

1. the lesson she struggled with -> the concepts it teaches;
2. those concepts -> their prerequisites, up to ``MAX_DEPTH`` hops;
3. each concept -> the objectives that teach it in a subject Scholr teaches;
4. each objective is scored by how much it needs the work, and how directly it sits under the weakness.

Ranking is by how much the objective needs work, not by how deep it sits. A prerequisite that is weaker
than the concept above it therefore comes first — the foundation is fixed before what stands on it (AC-X7) —
but when we know nothing about either, the answer is the idea the class was actually about, not something two
hops beneath it. An objective already secure is not a target at all (AC-X8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

MAX_DEPTH = 2
# One broad concept can teach many objectives. Without a cap, five near-identical foundation objectives crowd
# out the idea the class was actually about, which is not a useful answer to "what should I do about it?".
PER_CONCEPT_LIMIT = 2
# Same problem one level up: with four external courses being logged, the newest bad class would otherwise
# fill the whole list and the others would be invisible. Rather than a flat cap — which would throttle the
# feature when only one class has been logged — the list is built round-robin: the best suggestion from each
# class, then the second from each, and so on. With a single class that is just the ranked list.
# How fast an old class stops steering today's work.
HALF_LIFE_DAYS = 21.0

# How much an objective needs work, by mastery level (mastery.rules.MasteryLevel).
NEED_BY_LEVEL = {0: 1.0, 1: 1.0, 2: 0.8, 3: 0.45, 4: 0.15, 5: 0.1}
NEVER_PRACTISED_NEED = 0.8
OPEN_MISTAKE_NEED = 0.25
MAX_MISTAKE_NEED = 0.5
RETENTION_NEED = {"none": 0.0, "medium": 0.1, "high": 0.2}
SECURE_LEVEL = 4  # Mastered


@dataclass(frozen=True)
class Weakness:
    """One thing that did not go well in an external class, already attributed to a lesson."""

    objective_id: UUID  # the external lesson
    occurred_on: date
    severity: float  # 0..1, 1 = got none of it


@dataclass(frozen=True)
class ConceptGraph:
    """The slice of the concept graph a trace needs. All ids, no text beyond concept names."""

    concepts_of_objective: Mapping[UUID, tuple[UUID, ...]]
    prerequisites: Mapping[UUID, tuple[tuple[UUID, float], ...]]
    # Only objectives of subjects Scholr teaches or has planned, so a target can never be an external lesson
    # (AC-X10). "Planned" means Scholr knows the syllabus but has no questions for it yet.
    objectives_of_concept: Mapping[UUID, tuple[UUID, ...]]
    concept_names: Mapping[UUID, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Standing:
    """What we already know about the student on one objective Scholr teaches."""

    level: int | None = None  # None = never practised
    open_mistakes: int = 0
    retention_risk: str = "none"


@dataclass(frozen=True)
class Target:
    objective_id: UUID
    concept_id: UUID
    concept_name: str
    depth: int  # 0 = the concept the lesson taught, 1+ = a prerequisite of it
    priority: float
    from_objective_id: UUID  # the external lesson this came from


def need(standing: Standing) -> float:
    """0 = nothing to gain here, 1 = wide open."""
    base = NEVER_PRACTISED_NEED if standing.level is None else NEED_BY_LEVEL.get(standing.level, 0.5)
    extra = min(MAX_MISTAKE_NEED, OPEN_MISTAKE_NEED * standing.open_mistakes)
    return min(1.0, base + extra + RETENTION_NEED.get(standing.retention_risk, 0.0))


def is_secure(standing: Standing) -> bool:
    """Mastered, nothing open, nothing going stale — leave it alone (AC-X8)."""
    return (
        standing.level is not None
        and standing.level >= SECURE_LEVEL
        and standing.open_mistakes == 0
        and standing.retention_risk == "none"
    )


def recency_weight(occurred_on: date, today: date) -> float:
    age_days = max(0, (today - occurred_on).days)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def _reachable(graph: ConceptGraph, roots: Sequence[UUID]) -> dict[UUID, tuple[int, float]]:
    """Concept id -> (shallowest depth, strength of the path to it), breadth-first to MAX_DEPTH."""
    found: dict[UUID, tuple[int, float]] = {}
    frontier: list[tuple[UUID, float]] = [(concept_id, 1.0) for concept_id in roots]
    for depth in range(MAX_DEPTH + 1):
        next_frontier: list[tuple[UUID, float]] = []
        for concept_id, strength in frontier:
            seen = found.get(concept_id)
            if seen is not None and (seen[0] < depth or seen[1] >= strength):
                continue
            found[concept_id] = (depth, strength)
            if depth < MAX_DEPTH:
                next_frontier.extend(
                    (prerequisite_id, strength * prerequisite_strength)
                    for prerequisite_id, prerequisite_strength in graph.prerequisites.get(concept_id, ())
                )
        frontier = next_frontier
    return found


def targets(
    weaknesses: Sequence[Weakness],
    graph: ConceptGraph,
    standings: Mapping[UUID, Standing],
    *,
    today: date,
    limit: int | None = None,
) -> list[Target]:
    """Ranked objectives to reinforce. Same inputs always give the same list (AC-X6)."""
    best: dict[UUID, Target] = {}
    for weakness in weaknesses:
        weight = weakness.severity * recency_weight(weakness.occurred_on, today)
        if weight <= 0:
            continue
        roots = graph.concepts_of_objective.get(weakness.objective_id, ())
        for concept_id, (depth, strength) in _reachable(graph, roots).items():
            for objective_id in graph.objectives_of_concept.get(concept_id, ()):
                standing = standings.get(objective_id, Standing())
                if is_secure(standing):
                    continue
                # Rounded before comparing: float noise must not let a deeper concept displace a shallower
                # one on what is really a tie.
                priority = round(need(standing) * weight * strength, 6)
                current = best.get(objective_id)
                if current is None or priority > current.priority:
                    best[objective_id] = Target(
                        objective_id=objective_id,
                        concept_id=concept_id,
                        concept_name=graph.concept_names.get(concept_id, ""),
                        depth=depth,
                        priority=priority,
                        from_objective_id=weakness.objective_id,
                    )
    # Equal need: the closer the idea is to what the class taught, the more it sounds like an answer.
    ranked = sorted(best.values(), key=lambda t: (-t.priority, t.depth, str(t.objective_id)))
    by_source: dict[UUID, list[Target]] = {}
    for target in ranked:
        by_source.setdefault(target.from_objective_id, []).append(target)

    spread: list[Target] = []
    per_concept: dict[UUID, int] = {}
    while any(by_source.values()):
        for queue in by_source.values():
            while queue:
                target = queue.pop(0)
                if per_concept.get(target.concept_id, 0) >= PER_CONCEPT_LIMIT:
                    continue
                per_concept[target.concept_id] = per_concept.get(target.concept_id, 0) + 1
                spread.append(target)
                break
    return spread[:limit] if limit is not None else spread
