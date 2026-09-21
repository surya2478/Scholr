"""Skill profile rule v1 (pure)."""

from __future__ import annotations

import pytest

from app.modules.mastery.skills import SkillEvidence, skill_scores

WEIGHTS = {"AO1": 0.4, "AO2": 0.4, "AO3": 0.2}


def test_scores_use_syllabus_weights_and_cap_at_one() -> None:
    evidence = [
        SkillEvidence(10, {"AO1": 4, "AO2": 2, "AO3": 2}),  # AO1 4/4 = 1.0, AO2 2/4 = 0.5, AO3 2/2 = 1.0
        SkillEvidence(10, {"AO1": 6, "AO2": 1}),  # AO1 capped at 1.0, AO2 0.25, AO3 0.0
    ]
    scores = skill_scores(evidence, WEIGHTS)
    assert scores["AO1"].score == pytest.approx(1.0)
    assert scores["AO2"].score == pytest.approx(0.375)
    assert scores["AO3"].score == pytest.approx(0.5)
    assert all(s.evidence_count == 2 for s in scores.values())


def test_no_evidence_or_weights_gives_no_scores() -> None:
    assert skill_scores([], WEIGHTS) == {}
    assert skill_scores([SkillEvidence(4, {"AO1": 4})], {}) == {}
