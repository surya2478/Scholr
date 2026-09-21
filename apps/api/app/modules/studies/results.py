"""Validation-study results (PHASE-1 §5), pure: topic scores per form, normalized gain, retention ratio, eligibility,
engagement and the per-subject decision rule. The student interview and the cross-subject part of the rule
("no subject below −0.05") are judged by people from these numbers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from uuid import UUID

RULE_VERSION = "study_rule_2026-09-14"
MIN_SESSIONS_PER_WEEK = 3.0
GAIN_GO = 0.15
RETENTION_MARGIN = 0.05
ELIGIBLE_BASELINE = (0.20, 0.70)
STUDY_KINDS = ("baseline", "post", "retention")


@dataclass(frozen=True)
class MarkedItem:
    objective_ids: frozenset[UUID]
    marks: int
    awarded: float | None  # None: answered but no final/reviewed mark yet; unanswered items carry 0


@dataclass(frozen=True)
class FormSitting:
    kind: str  # baseline | post | retention
    form_code: str | None
    submitted_at: datetime
    items: tuple[MarkedItem, ...]


@dataclass(frozen=True)
class TopicScore:
    awarded: float
    available: int
    provisional: bool

    @property
    def ratio(self) -> float:
        return self.awarded / self.available


@dataclass(frozen=True)
class Assignment:
    pair_code: str
    arm: str  # app | control
    objective_ids: frozenset[UUID]


@dataclass(frozen=True)
class ArmResult:
    pair_code: str
    arm: str
    baseline: TopicScore | None
    post: TopicScore | None
    retention: TopicScore | None
    gain: float | None
    retention_ratio: float | None
    eligible: bool | None  # baseline between 20% and 70% of the marks
    overlapping_items: int  # items tagged across this topic and another: excluded from the score


@dataclass(frozen=True)
class SubjectDecision:
    decision: str  # pending | go_candidate | iterate | no_gain
    reasons: list[str]
    provisional: bool
    sessions_per_week: float | None
    app_hours: float
    mean_gain_app: float | None
    mean_gain_control: float | None
    gain_difference: float | None
    mean_retention_app: float | None
    mean_retention_control: float | None
    learning_per_hour: float | None
    rule_version: str = field(default=RULE_VERSION)


def topic_score(sitting: FormSitting | None, objectives: frozenset[UUID]) -> tuple[TopicScore | None, int]:
    """Score of the items wholly inside the topic; items that also touch other objectives are counted separately."""
    if sitting is None:
        return None, 0
    inside = [i for i in sitting.items if i.objective_ids and i.objective_ids <= objectives]
    overlapping = sum(1 for i in sitting.items if i.objective_ids & objectives and not i.objective_ids <= objectives)
    if not inside:
        return None, overlapping
    return (
        TopicScore(
            awarded=sum(i.awarded or 0 for i in inside),
            available=sum(i.marks for i in inside),
            provisional=any(i.awarded is None for i in inside),
        ),
        overlapping,
    )


def normalized_gain(baseline: TopicScore | None, post: TopicScore | None) -> float | None:
    if baseline is None or post is None or baseline.ratio >= 1:
        return None
    return (post.ratio - baseline.ratio) / (1 - baseline.ratio)


def retention_ratio(post: TopicScore | None, retention: TopicScore | None) -> float | None:
    if post is None or retention is None or post.ratio == 0:
        return None
    return retention.ratio / post.ratio


def latest_sittings(sittings: Sequence[FormSitting]) -> dict[str, FormSitting]:
    latest: dict[str, FormSitting] = {}
    for sitting in sorted(sittings, key=lambda x: x.submitted_at):
        latest[sitting.kind] = sitting
    return latest


def arm_results(assignments: Sequence[Assignment], sittings: Sequence[FormSitting]) -> list[ArmResult]:
    forms = latest_sittings(sittings)
    results = []
    for a in sorted(assignments, key=lambda x: (x.pair_code, x.arm)):
        scores = {kind: topic_score(forms.get(kind), a.objective_ids) for kind in STUDY_KINDS}
        baseline, post, retention = (scores[k][0] for k in STUDY_KINDS)
        low, high = ELIGIBLE_BASELINE
        results.append(
            ArmResult(
                pair_code=a.pair_code,
                arm=a.arm,
                baseline=baseline,
                post=post,
                retention=retention,
                gain=normalized_gain(baseline, post),
                retention_ratio=retention_ratio(post, retention),
                eligible=None if baseline is None else low <= baseline.ratio <= high,
                overlapping_items=sum(scores[k][1] for k in STUDY_KINDS),
            )
        )
    return results


def engagement(
    session_starts: Sequence[datetime],
    active_minutes: Sequence[tuple[datetime, int]],
    *,
    start: datetime | None,
    end: datetime,
) -> tuple[float | None, float]:
    """Sessions per week and app hours inside the intervention window (baseline submitted -> post submitted)."""
    if start is None or end <= start:
        return None, 0.0
    weeks = max((end - start).total_seconds() / (7 * 86400), 1 / 7)
    sessions = sum(1 for at in session_starts if start <= at <= end)
    minutes = sum(m for at, m in active_minutes if start <= at <= end)
    return sessions / weeks, minutes / 60


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return mean(present) if present else None


def decide(arms: Sequence[ArmResult], *, sessions_per_week: float | None, app_hours: float) -> SubjectDecision:
    gain_app = _mean([a.gain for a in arms if a.arm == "app"])
    gain_control = _mean([a.gain for a in arms if a.arm == "control"])
    retention_app = _mean([a.retention_ratio for a in arms if a.arm == "app"])
    retention_control = _mean([a.retention_ratio for a in arms if a.arm == "control"])
    difference = None if gain_app is None or gain_control is None else gain_app - gain_control
    provisional = any(s is not None and s.provisional for a in arms for s in (a.baseline, a.post, a.retention))
    reasons: list[str] = []
    if any(a.eligible is False for a in arms):
        reasons.append("topic_baseline_outside_20_70")
    if any(a.overlapping_items for a in arms):
        reasons.append("items_span_topics")

    if difference is None:
        decision = "pending"
        reasons.append("baseline_or_post_missing")
    elif sessions_per_week is None or sessions_per_week < MIN_SESSIONS_PER_WEEK:
        decision = "iterate"
        reasons.append("engagement_below_3_sessions_per_week")
    elif difference >= GAIN_GO:
        if retention_app is None or retention_control is None:
            decision = "pending"
            reasons.append("retention_test_missing")
        elif retention_app >= retention_control - RETENTION_MARGIN:
            decision = "go_candidate"
            reasons += ["needs_student_interview", "check_no_subject_below_minus_0.05"]
        else:
            decision = "iterate"
            reasons.append("retention_below_control")
    elif difference <= 0:
        decision = "no_gain"  # STOP/RETHINK only if this holds in both subjects
        reasons.append("gain_difference_not_positive")
    else:
        decision = "iterate"
        reasons.append("gain_difference_below_0.15")
    if provisional:
        reasons.append("scores_provisional")
    return SubjectDecision(
        decision=decision,
        reasons=reasons,
        provisional=provisional,
        sessions_per_week=sessions_per_week,
        app_hours=app_hours,
        mean_gain_app=gain_app,
        mean_gain_control=gain_control,
        gain_difference=difference,
        mean_retention_app=retention_app,
        mean_retention_control=retention_control,
        learning_per_hour=None if difference is None or app_hours <= 0 else difference / app_hours,
    )
