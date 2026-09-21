"""Skill profile rule v1 (pure): how well the student performs on each assessment objective.

Evidence is a final (or reviewed) evaluation whose marks are split by skill. For one answer, a skill's share of the
available marks is taken from the syllabus weighting (subject config ``skill_weights``); the skill scores
``awarded_for_skill / (marks_available × weight)``, capped at 1. The profile score is the mean over evidence.
Pipelines that do not split marks by skill (structured_math today) produce no skill evidence.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

RULE_VERSION = "skills_v1"


@dataclass(frozen=True)
class SkillEvidence:
    marks_available: float
    skill_marks: Mapping[str, float]


@dataclass(frozen=True)
class SkillScore:
    score: float
    evidence_count: int


def skill_scores(evidence: Sequence[SkillEvidence], weights: Mapping[str, float]) -> dict[str, SkillScore]:
    totals: dict[str, list[float]] = defaultdict(list)
    for item in evidence:
        if item.marks_available <= 0:
            continue
        for code, weight in weights.items():
            if weight <= 0:
                continue
            awarded = item.skill_marks.get(code, 0.0)
            totals[code].append(min(1.0, max(0.0, awarded) / (item.marks_available * weight)))
    return {code: SkillScore(round(sum(v) / len(v), 3), len(v)) for code, v in totals.items() if v}
