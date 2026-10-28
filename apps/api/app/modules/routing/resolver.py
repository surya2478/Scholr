"""Master Router, deterministic part (ARCHITECTURE §7).

Order: assessment lock → session context → keyword rules → (LLM classifier) → ask student.
This module never calls an LLM; it reports when classification is needed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

RouteSource = Literal["assessment_lock", "session", "rules", "needs_classifier"]

# Assessments where the tutor must not help (validation study and exams).
NO_HELP_ASSESSMENT_KINDS = frozenset({"baseline", "post", "retention", "exam_style", "topic_exam"})


@dataclass(frozen=True)
class RoutingContext:
    enrolled_subject_codes: Sequence[str]
    session_subject_code: str | None = None
    session_objective_id: UUID | None = None
    active_assessment_id: UUID | None = None
    active_assessment_kind: str | None = None
    active_assessment_subject_code: str | None = None


@dataclass(frozen=True)
class Route:
    source: RouteSource
    subject_code: str | None
    objective_id: UUID | None
    tutoring_allowed: bool
    candidates: tuple[str, ...] = field(default=())


_TOKEN = re.compile(r"[a-z][a-z'-]+")


def keyword_scores(text: str, index: Mapping[str, Sequence[str]]) -> dict[str, int]:
    """Count syllabus-term matches per subject. Multi-word terms match as phrases."""
    lowered = text.lower()
    tokens = set(_TOKEN.findall(lowered))
    scores: dict[str, int] = {}
    for subject, terms in index.items():
        n = 0
        for term in terms:
            t = term.lower()
            if " " in t:
                n += 1 if t in lowered else 0
            elif t in tokens:
                n += 1
        if n:
            scores[subject] = n
    return scores


def resolve(ctx: RoutingContext, text: str, keyword_index: Mapping[str, Sequence[str]]) -> Route:
    if ctx.active_assessment_id is not None:
        allowed = (ctx.active_assessment_kind or "") not in NO_HELP_ASSESSMENT_KINDS
        return Route(
            "assessment_lock",
            ctx.active_assessment_subject_code or ctx.session_subject_code,
            None,
            tutoring_allowed=allowed,
        )

    if ctx.session_subject_code is not None:
        return Route("session", ctx.session_subject_code, ctx.session_objective_id, True)

    enrolled = {s: keyword_index.get(s, ()) for s in ctx.enrolled_subject_codes}
    scores = keyword_scores(text, enrolled)
    if scores:
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best, best_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        if best_score >= 2 and best_score >= 2 * runner_up or best_score >= 1 and runner_up == 0:
            return Route("rules", best, None, True)
        return Route("needs_classifier", None, None, True, tuple(s for s, _ in ranked))

    return Route("needs_classifier", None, None, True, tuple(ctx.enrolled_subject_codes))
