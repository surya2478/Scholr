"""Mastery rule v1 (ARCHITECTURE §13). Pure, deterministic, versioned.

Mastery is a projection of evidence. This module only computes; persistence and
event handling live in the mastery service.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Literal

RetentionRisk = Literal["none", "medium", "high"]


class MasteryLevel(IntEnum):
    NOT_INTRODUCED = 0
    INTRODUCED = 1
    DEVELOPING = 2
    COMPETENT = 3
    MASTERED = 4
    ADVANCED = 5


LEVEL_NAMES = {
    MasteryLevel.NOT_INTRODUCED: "Not introduced",
    MasteryLevel.INTRODUCED: "Introduced",
    MasteryLevel.DEVELOPING: "Developing",
    MasteryLevel.COMPETENT: "Competent",
    MasteryLevel.MASTERED: "Mastered",
    MasteryLevel.ADVANCED: "Advanced",
}


@dataclass(frozen=True)
class EvidenceItem:
    """One evaluated attempt on a learning objective."""

    occurred_at: datetime
    score: float  # marks_awarded / marks_available, 0..1
    help_level: int  # max help level used, 0..5 (see tutoring.policy)
    evaluation_confidence: float  # 0..1
    exam_style: bool = False
    stretch: bool = False
    retention_check: bool = False


@dataclass(frozen=True)
class MasteryConfig:
    rule_version: str = "default_v1"
    half_life_days: float = 30.0
    exam_style_weight: float = 1.25
    assistance_multipliers: tuple[float, ...] = (1.0, 0.9, 0.7, 0.5, 0.3, 0.1)
    independent_success_score: float = 0.8
    independent_max_help: int = 1
    competent_score: float = 0.6
    competent_independent: int = 2
    competent_min_attempts: int = 3
    developing_min_attempts: int = 3
    mastered_score: float = 0.8
    mastered_independent: int = 3
    mastered_distinct_days: int = 2
    advanced_stretch_successes: int = 2
    retention_failure_score: float = 0.5
    confidence_evidence_target: float = 8.0
    retention_medium_days: int = 21
    retention_high_days: int = 45


DEFAULT_CONFIG = MasteryConfig()


@dataclass(frozen=True)
class MasteryResult:
    level: MasteryLevel
    score: float
    mastery_confidence: float
    evidence_count: int
    independent_successes: int
    distinct_days: int
    last_demonstrated_at: datetime | None
    retention_risk: RetentionRisk
    rule_version: str
    reasons: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class _Stats:
    score: float
    recency_total: float
    attempts: int
    independent: int
    distinct_days: int
    exam_success: bool
    stretch_successes: int
    last_demonstrated: datetime | None


def _is_independent_success(item: EvidenceItem, cfg: MasteryConfig) -> bool:
    return item.score >= cfg.independent_success_score and item.help_level <= cfg.independent_max_help


def _stats(items: Sequence[EvidenceItem], now: datetime, cfg: MasteryConfig) -> _Stats:
    weighted_sum = weight_total = recency_total = 0.0
    for item in items:
        age_days = max(0.0, (now - item.occurred_at).total_seconds() / 86400)
        recency = 0.5 ** (age_days / cfg.half_life_days)
        exam = cfg.exam_style_weight if item.exam_style else 1.0
        help_idx = min(max(item.help_level, 0), len(cfg.assistance_multipliers) - 1)
        assist = cfg.assistance_multipliers[help_idx]
        weighted_sum += recency * exam * max(0.0, min(1.0, item.score)) * assist
        weight_total += recency * exam
        recency_total += recency
    successes = [e for e in items if _is_independent_success(e, cfg)]
    return _Stats(
        score=weighted_sum / weight_total if weight_total else 0.0,
        recency_total=recency_total,
        attempts=len(items),
        independent=len(successes),
        distinct_days=len({e.occurred_at.date() for e in successes}),
        exam_success=any(e.exam_style for e in successes),
        stretch_successes=sum(1 for e in successes if e.stretch),
        last_demonstrated=successes[-1].occurred_at if successes else None,
    )


def _level(s: _Stats, cfg: MasteryConfig, has_open_high_severity_mistake: bool) -> MasteryLevel:
    if (
        s.score >= cfg.mastered_score
        and s.independent >= cfg.mastered_independent
        and s.distinct_days >= cfg.mastered_distinct_days
        and s.exam_success
        and not has_open_high_severity_mistake
    ):
        if s.stretch_successes >= cfg.advanced_stretch_successes:
            return MasteryLevel.ADVANCED
        return MasteryLevel.MASTERED
    if (
        s.score >= cfg.competent_score
        and s.independent >= cfg.competent_independent
        and s.attempts >= cfg.competent_min_attempts
    ):
        return MasteryLevel.COMPETENT
    if s.attempts >= cfg.developing_min_attempts:
        return MasteryLevel.DEVELOPING
    return MasteryLevel.INTRODUCED


def compute_mastery(
    evidence: Sequence[EvidenceItem],
    *,
    now: datetime,
    explanation_viewed: bool = False,
    has_open_high_severity_mistake: bool = False,
    min_evaluation_confidence: float = 0.0,
    config: MasteryConfig = DEFAULT_CONFIG,
) -> MasteryResult:
    cfg = config
    items = sorted(
        (e for e in evidence if e.evaluation_confidence >= min_evaluation_confidence),
        key=lambda e: e.occurred_at,
    )
    if not items:
        level = MasteryLevel.INTRODUCED if explanation_viewed else MasteryLevel.NOT_INTRODUCED
        return MasteryResult(level, 0.0, 0.0, 0, 0, 0, None, "none", cfg.rule_version, ())

    reasons: list[str] = []
    stats = _stats(items, now, cfg)
    level = _level(stats, cfg, has_open_high_severity_mistake)
    if has_open_high_severity_mistake and level == MasteryLevel.COMPETENT and stats.score >= cfg.mastered_score:
        reasons.append("held_at_competent_open_high_severity_mistake")

    retention_checks = [e for e in items if e.retention_check]
    if retention_checks:
        latest = retention_checks[-1]
        failed = latest.score < cfg.retention_failure_score
        after_success = stats.last_demonstrated is None or latest.occurred_at >= stats.last_demonstrated
        if failed and after_success:
            prior_items = [e for e in items if e is not latest]
            prior = _level(_stats(prior_items, now, cfg), cfg, has_open_high_severity_mistake)
            if prior >= MasteryLevel.COMPETENT:
                level = MasteryLevel(min(level, prior - 1))
                reasons.append("failed_retention_check")

    risk: RetentionRisk = "none"
    if level >= MasteryLevel.COMPETENT and stats.last_demonstrated is not None:
        idle_days = (now - stats.last_demonstrated).total_seconds() / 86400
        if idle_days > cfg.retention_high_days:
            risk = "high"
        elif idle_days > cfg.retention_medium_days:
            risk = "medium"

    mean_conf = sum(e.evaluation_confidence for e in items) / stats.attempts
    confidence = min(1.0, stats.recency_total / cfg.confidence_evidence_target) * mean_conf

    return MasteryResult(
        level=level,
        score=round(stats.score, 4),
        mastery_confidence=round(confidence, 4),
        evidence_count=stats.attempts,
        independent_successes=stats.independent,
        distinct_days=stats.distinct_days,
        last_demonstrated_at=stats.last_demonstrated,
        retention_risk=risk,
        rule_version=cfg.rule_version,
        reasons=tuple(reasons),
    )
