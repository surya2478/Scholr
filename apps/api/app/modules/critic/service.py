"""Study Critic: patterns in how she studies, drawn from events (Phase 2, AC-C1..C3).

Stores nothing, calls no LLM. The wording comes from `patterns.yaml` templates — the same observation is
phrased for the student and for the guardian, and both see the same list (AC-C3, and AC-S6 before it).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy.orm import Session

from app.core.rbac import Principal, require_student_access
from app.modules.critic import rules
from app.modules.critic.schemas import CriticOut, PatternOut
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.events import service as events
from app.modules.identity import service as identity
from app.tools.dates import local_date

SCOPE = "progress"
PATTERNS_FILE = Path(__file__).with_name("patterns.yaml")
# The help levels that count as "needed help" — a nudge does not, a hint or more does (tutoring.policy).
HELPED_FROM_LEVEL = 2
EVENT_TYPES = (
    "session_ended",
    "attempt_evaluated",
    "plan_item_completed",
    "plan_item_skipped",
)


@lru_cache
def templates() -> dict[str, Any]:
    return yaml.safe_load(PATTERNS_FILE.read_text(encoding="utf-8"))


def _day_activity(
    s: Session, *, student_id: UUID, since: date, until: date, timezone: str
) -> tuple[list[rules.DayActivity], dict[UUID, int]]:
    """One row per day in the window, plus study minutes per subject."""
    minutes: dict[date, int] = defaultdict(int)
    answers: dict[date, int] = defaultdict(int)
    helped: dict[date, int] = defaultdict(int)
    planned: dict[date, int] = defaultdict(int)
    finished: dict[date, int] = defaultdict(int)
    by_subject: dict[UUID, int] = defaultdict(int)

    for ev in events.list_events(s, student_id=student_id, types=EVENT_TYPES):
        day = local_date(ev.occurred_at, timezone)
        if day < since or day > until:
            continue
        if ev.type == "session_ended":
            active = int(ev.payload.get("active_minutes") or 0)
            minutes[day] += active
            if ev.subject_id:
                by_subject[ev.subject_id] += active
        elif ev.type == "attempt_evaluated":
            payload = events.AttemptEvaluated.model_validate(ev.payload)
            if payload.status != "final":
                continue
            answers[day] += 1
            if payload.help_level >= HELPED_FROM_LEVEL:
                helped[day] += 1
        elif ev.type == "plan_item_completed":
            planned[day] += 1
            finished[day] += 1
        elif ev.type == "plan_item_skipped":
            planned[day] += 1

    days = []
    cursor = since
    while cursor <= until:
        days.append(
            rules.DayActivity(
                day=cursor,
                study_minutes=minutes[cursor],
                answers=answers[cursor],
                answers_with_help=helped[cursor],
                plan_items=planned[cursor],
                plan_items_done=finished[cursor],
            )
        )
        cursor += timedelta(days=1)
    return days, by_subject


def _subject_activity(s: Session, *, student_id: UUID, by_subject: dict[UUID, int]) -> list[rules.SubjectActivity]:
    """Every enrolled subject, including one with no minutes at all — that silence is the point."""
    subject_ids = [e.subject_id for e in enrollment.list_enrollments(s, [student_id])]
    summaries = curriculum.subject_summaries(s, subject_ids)
    return [
        rules.SubjectActivity(
            subject_id=str(subject_id),
            subject_name=summaries[subject_id].name,
            study_minutes=by_subject.get(subject_id, 0),
        )
        for subject_id in subject_ids
        if subject_id in summaries
    ]


def _out(pattern: rules.Pattern, *, audience: str) -> PatternOut:
    template = templates()["patterns"][pattern.kind]
    return PatternOut(
        kind=pattern.kind,
        severity=pattern.severity,
        title=template["title"],
        observation=template[audience].format(**pattern.facts).strip(),
        why=template["why"],
        window_days=pattern.window_days,
        rule_version=pattern.rule_version,
        facts={k: str(v) for k, v in pattern.facts.items()},
    )


def critique(
    s: Session, principal: Principal, *, student_id: UUID, now: datetime, audience: str | None = None
) -> CriticOut:
    require_student_access(principal, student_id, SCOPE)
    timezone = identity.student_timezone(s, student_id)
    until = local_date(now, timezone)
    since = until - timedelta(days=rules.WINDOW_DAYS - 1)

    days, by_subject = _day_activity(s, student_id=student_id, since=since, until=until, timezone=timezone)
    subjects = _subject_activity(s, student_id=student_id, by_subject=by_subject)
    found = rules.patterns(days, subjects)

    voice = audience or ("student" if principal.role == "student" else "guardian")
    totals = rules.counts(days)
    return CriticOut(
        window_days=rules.WINDOW_DAYS,
        from_day=since,
        to_day=until,
        rule_version=rules.RULE_VERSION,
        template_version=templates()["version"],
        patterns=[_out(p, audience=voice) for p in found],
        nothing_stands_out=templates()["nothing"][voice] if not found else None,
        active_days=totals["active_days"],
        study_minutes=totals["study_minutes"],
        answers=totals["answers"],
    )
