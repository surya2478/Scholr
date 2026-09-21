"""Hybrid retrieval ranking and context validation state (ARCHITECTURE §9.3–9.4). Pure functions.

Phase 1 uses reciprocal rank fusion of vector and full-text rankings with no separate reranker model (cost);
the state rules use cosine similarity, authority tier and objective alignment. Thresholds live in subject configs
and must be calibrated on the retrieval eval set.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

RRF_K = 60
ALIGNMENT_BONUS = 1.0 / RRF_K  # an objective-aligned chunk ranks like one extra first-place vote
GROUNDING_TIERS = frozenset({"A", "B", "C"})  # tier D (student notes) and E never ground correctness

RetrievalState = str  # "HIGH" | "MEDIUM" | "LOW" | "NONE"


def reciprocal_rank_fusion(rankings: Sequence[Sequence[Hashable]], k: int = RRF_K) -> dict[Hashable, float]:
    scores: dict[Hashable, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (k + rank)
    return dict(scores)


@dataclass(frozen=True)
class Candidate:
    similarity: float | None  # cosine similarity from the vector search; None if found by full text only
    keyword_match: bool
    aligned: bool  # tagged with a requested objective (or topic)
    tier: str


@dataclass(frozen=True)
class StateThresholds:
    high: float
    medium: float
    low: float


def retrieval_state(
    candidates: Sequence[Candidate], *, objective_scoped: bool, thresholds: StateThresholds
) -> RetrievalState:
    def grounded(c: Candidate, floor: float) -> bool:
        return c.tier in GROUNDING_TIERS and c.similarity is not None and c.similarity >= floor

    strong = [c for c in candidates if grounded(c, thresholds.high) and (c.aligned or not objective_scoped)]
    if len(strong) >= 2:
        return "HIGH"
    medium = [c for c in candidates if grounded(c, thresholds.medium)]
    if medium and (not objective_scoped or any(c.aligned for c in medium)):
        return "MEDIUM"
    if any(grounded(c, thresholds.low) or (c.keyword_match and c.tier in GROUNDING_TIERS) for c in candidates):
        return "LOW"
    return "NONE"
