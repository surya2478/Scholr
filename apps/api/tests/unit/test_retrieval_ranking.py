from __future__ import annotations

from app.modules.knowledge.ranking import Candidate, StateThresholds, reciprocal_rank_fusion, retrieval_state

T = StateThresholds(high=0.6, medium=0.5, low=0.4)


def test_rrf_rewards_items_found_by_both_rankings() -> None:
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["c", "d"]])
    assert max(scores, key=scores.__getitem__) == "c"
    assert scores["a"] > scores["b"] == scores["d"]  # same rank in different lists scores the same


def c(similarity: float | None, *, aligned: bool = True, tier: str = "B", keyword: bool = False) -> Candidate:
    return Candidate(similarity=similarity, keyword_match=keyword, aligned=aligned, tier=tier)


def test_high_needs_two_strong_aligned_grounding_chunks() -> None:
    assert retrieval_state([c(0.7), c(0.65)], objective_scoped=True, thresholds=T) == "HIGH"
    assert retrieval_state([c(0.7), c(0.65, aligned=False)], objective_scoped=True, thresholds=T) == "MEDIUM"
    assert retrieval_state([c(0.7), c(0.65, aligned=False)], objective_scoped=False, thresholds=T) == "HIGH"


def test_medium_requires_alignment_when_scoped() -> None:
    assert retrieval_state([c(0.55)], objective_scoped=True, thresholds=T) == "MEDIUM"
    assert retrieval_state([c(0.55, aligned=False)], objective_scoped=True, thresholds=T) == "LOW"


def test_low_and_none() -> None:
    assert retrieval_state([c(0.45)], objective_scoped=False, thresholds=T) == "LOW"
    assert retrieval_state([c(None, keyword=True)], objective_scoped=False, thresholds=T) == "LOW"
    assert retrieval_state([c(0.3)], objective_scoped=False, thresholds=T) == "NONE"
    assert retrieval_state([], objective_scoped=False, thresholds=T) == "NONE"


def test_student_notes_never_ground() -> None:
    assert retrieval_state([c(0.9, tier="D"), c(0.9, tier="D")], objective_scoped=False, thresholds=T) == "NONE"
