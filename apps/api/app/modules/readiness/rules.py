"""Exam readiness rule v1 (AC-R2). Pure, deterministic, versioned.

Readiness answers one question: on the work she has actually done, how is she placed against the way the
exam is weighted? Two honest limits are built in.

1. **Too little evidence is said, not hidden.** A band of "unknown" is a real answer; a confident 0% from
   three answers is not. `MIN_MARKS` is the floor below which nothing is claimed.
2. **Only marks that were split by assessment objective count.** A marker that returned an AO split gives
   real per-AO evidence. Spreading a whole-question mark equally across its AOs would invent data, so
   questions without a split are counted as coverage only — she has met them, but they say nothing about
   which AO is weak.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

RULE_VERSION = "readiness_v1"

# Below this many available marks on an objective, nothing is claimed about it.
MIN_MARKS = 20.0
# Our own bands, not Cambridge's: the syllabus publishes no readiness scale, only grade thresholds per
# session. They are deliberately cautious — "secure" means comfortably above half marks, not a predicted A.
SECURE = 0.65
DEVELOPING = 0.45

Band = Literal["secure", "developing", "weak", "unknown"]


@dataclass(frozen=True)
class MarkSplit:
    """One marked answer, with the marks the marker attributed to each assessment objective."""

    marks_available: float
    per_skill: Mapping[str, float]  # skill code -> marks awarded
    skill_codes: tuple[str, ...]  # every AO the question carries, split or not


@dataclass(frozen=True)
class SkillReadiness:
    skill_code: str
    share: float | None  # marks she gets, 0..1; None when there is too little to say
    weighting: float | None  # the exam's own weighting for this AO, 0..1
    band: Band
    answers_with_split: int
    answers_seen: int
    marks_available: float
    marks_awarded: float

    @property
    def shortfall(self) -> float | None:
        """How far the share sits below the exam's weighting is meaningless; this is the gap to `SECURE`."""
        return None if self.share is None else round(max(0.0, SECURE - self.share), 4)


def band_for(share: float | None, marks_available: float) -> Band:
    if share is None or marks_available < MIN_MARKS:
        return "unknown"
    if share >= SECURE:
        return "secure"
    if share >= DEVELOPING:
        return "developing"
    return "weak"


def skill_readiness(
    splits: Sequence[MarkSplit],
    *,
    skill_codes: Sequence[str],
    weightings: Mapping[str, float] | None = None,
) -> list[SkillReadiness]:
    """One row per assessment objective, in the order the caller gives them."""
    weightings = weightings or {}
    out: list[SkillReadiness] = []
    for code in skill_codes:
        awarded = available = 0.0
        with_split = seen = 0
        for split in splits:
            if code not in split.skill_codes:
                continue
            seen += 1
            if code in split.per_skill:
                with_split += 1
                awarded += split.per_skill[code]
                available += split.marks_available
        share = round(awarded / available, 4) if available > 0 else None
        out.append(
            SkillReadiness(
                skill_code=code,
                share=share,
                weighting=weightings.get(code),
                band=band_for(share, available),
                answers_with_split=with_split,
                answers_seen=seen,
                marks_available=round(available, 2),
                marks_awarded=round(awarded, 2),
            )
        )
    return out


@dataclass(frozen=True)
class TopicEvidence:
    topic_code: str
    topic_name: str
    marks_awarded: float
    marks_available: float
    answers: int
    objectives_total: int
    objectives_secure: int


@dataclass(frozen=True)
class TopicReadiness:
    topic_code: str
    topic_name: str
    share: float | None
    band: Band
    answers: int
    objectives_total: int
    objectives_secure: int


def topic_readiness(evidence: Sequence[TopicEvidence]) -> list[TopicReadiness]:
    rows = []
    for e in evidence:
        share = round(e.marks_awarded / e.marks_available, 4) if e.marks_available > 0 else None
        rows.append(
            TopicReadiness(
                topic_code=e.topic_code,
                topic_name=e.topic_name,
                share=share,
                band=band_for(share, e.marks_available),
                answers=e.answers,
                objectives_total=e.objectives_total,
                objectives_secure=e.objectives_secure,
            )
        )
    return rows


def weighted_share(skills: Sequence[SkillReadiness]) -> float | None:
    """A single estimate: her share on each AO, weighted the way the exam weights that AO.

    Only objectives with enough evidence count, and the weights are renormalised over those — so this is
    "on what we can judge", never a whole-paper prediction. None until something can be judged.
    """
    judged = [s for s in skills if s.share is not None and s.weighting and s.band != "unknown"]
    total_weight = sum(s.weighting or 0.0 for s in judged)
    if not judged or total_weight <= 0:
        return None
    return round(sum((s.weighting or 0.0) * (s.share or 0.0) for s in judged) / total_weight, 4)


def coverage(answered_topics: int, total_topics: int) -> float:
    return round(answered_topics / total_topics, 4) if total_topics else 0.0
