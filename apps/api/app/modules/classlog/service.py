"""What did class cover today? One card, two taps (docs/GO-LIVE-ENGAGEMENT.md F4, improvement 7).

Each school day she taps which chapter each of her school subjects covered. The tap is stored as her own entry in
the teaching plan (source "class check-in"), current for a week: the card links straight to the chapter that
evening, while it is cheapest to lock in, and from the next plan on the planner's school-topic rule offers it for
the week. Over a term the dated entries are the week-by-week scheme of work nobody has (CONTEXT U2).

Deterministic: the suggestions are the chapter she logged last (classes usually carry on), then the chapters after
it in syllabus order, kept inside the school's current term list when a parent has entered one. No model, and no
subject is named: the subjects asked about are the enrolled ones Scholr teaches or explains (stage), not a stream.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_student_access
from app.modules.classlog.schemas import ChapterOut, ClassCheckInIn, ClassCheckInOut, ClassSubjectOut, LoggedOut
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.enrollment.schemas import TeachingEntryIn
from app.modules.identity import service as identity
from app.modules.mastery import service as mastery
from app.modules.mastery.rules import MasteryLevel
from app.modules.subjects import service as subjects
from app.tools.dates import local_date

SOURCE = "class check-in"
CURRENT_FOR_DAYS = 7  # a chapter class covered stays "what you're learning at school" for a week
MAX_SUGGESTIONS = 4
SCOPE = "plans"
ASKED_STAGES = ("taught", "lessons")  # school subjects Scholr teaches or explains; never a stream by name


def school_day(day: date) -> bool:
    return day.weekday() < 5  # Monday to Friday


def chapters(tree: Any) -> list[Any]:
    """The level a class covers in a lesson: each top-level topic's children (a unit's chapters), in syllabus order.
    `tree` is a curriculum SubjectTreeOut."""
    out: list[Any] = []
    for root in tree.topics:
        out.extend(root.children or [root])
    return out


def suggest(order: Sequence[UUID], *, term: set[UUID], last: UUID | None) -> list[UUID]:
    """The likeliest chapters for today, best first: the one logged last, then those after it, then the rest.

    `order` is every chapter in syllabus order; `term` the school's current term list, when a parent entered one
    (an empty set means none, so every chapter is in play)."""
    pool = [c for c in order if c in term] if term else list(order)
    if not pool:
        pool = list(order)
    if last in pool:
        at = pool.index(last)
        pool = [*pool[at:], *pool[:at]]
    return pool[:MAX_SUGGESTIONS]


def _subjects(s: Session, student_id: UUID) -> list[tuple[UUID, str]]:
    enrolled = [e.subject_id for e in enrollment.list_enrollments(s, [student_id])]
    found = []
    for subject_id, summary in curriculum.subject_summaries(s, enrolled).items():
        try:
            stage = subjects.config_for(summary.code).stage
        except subjects.SubjectConfigError:
            continue
        if stage in ASKED_STAGES:
            found.append((subject_id, summary.name))
    return sorted(found, key=lambda x: x[1])


def _next_objective(s: Session, student_id: UUID, subject_id: UUID, topic_id: UUID) -> tuple[UUID, str] | None:
    """The first topic in the chapter she is not yet secure in."""
    levels = {m.objective_id: m.level for m in mastery.list_mastery(s, student_id=student_id, subject_id=subject_id)}
    objectives = sorted(
        curriculum.objectives_under_topics(s, [topic_id]), key=lambda o: curriculum.code_sort_key(o.code)
    )
    for o in objectives:
        if levels.get(o.id, 0) < int(MasteryLevel.COMPETENT):
            return o.id, o.code
    return None


def _term_chapters(tree: Any, entries: Sequence[Any], day: date, by_id: dict[UUID, Any]) -> set[UUID]:
    """The school's own term list for today (entered by a parent), expanded from units to their chapters."""
    term: set[UUID] = set()
    for e in entries:
        if e.source == SOURCE or (e.starts_on and e.starts_on > day) or (e.ends_on and e.ends_on < day):
            continue
        for t in e.topic_ids:
            if t in by_id:
                term.add(t)
                continue
            for root in tree.topics:
                if root.id == t:
                    term.update(n.id for n in (root.children or [root]))
    return term


def _subject_out(s: Session, student_id: UUID, subject_id: UUID, name: str, day: date) -> ClassSubjectOut | None:
    tree = curriculum.subject_tree(s, subject_id)
    if tree is None:
        return None
    nodes = chapters(tree)
    by_id = {n.id: n for n in nodes}
    entries = [e for e in enrollment.list_teaching_entries(s, student_id=student_id) if e.subject_id == subject_id]
    logs = sorted((e for e in entries if e.source == SOURCE and e.starts_on), key=lambda e: e.starts_on)
    last = next((t for e in reversed(logs) for t in e.topic_ids if t in by_id), None)
    suggested = suggest([n.id for n in nodes], term=_term_chapters(tree, entries, day, by_id), last=last)

    logged = []
    for e in logs:
        if e.starts_on != day:
            continue
        for t in e.topic_ids:
            node = by_id.get(t)
            if node is None:
                continue
            nxt = _next_objective(s, student_id, subject_id, t)
            logged.append(
                LoggedOut(
                    entry_id=e.id,
                    topic_id=t,
                    code=node.code,
                    name=node.name,
                    next_objective_id=nxt[0] if nxt else None,
                    next_objective_code=nxt[1] if nxt else None,
                )
            )
    return ClassSubjectOut(
        subject_id=subject_id,
        subject_name=name,
        logged=logged,
        suggestions=[ChapterOut(topic_id=t, code=by_id[t].code, name=by_id[t].name) for t in suggested],
        others=[ChapterOut(topic_id=n.id, code=n.code, name=n.name) for n in nodes if n.id not in suggested],
    )


def today(s: Session, principal: Principal, *, student_id: UUID, now: datetime) -> ClassCheckInOut:
    require_student_access(principal, student_id, SCOPE)
    day = local_date(now, identity.student_timezone(s, student_id))
    found = [_subject_out(s, student_id, sid, name, day) for sid, name in _subjects(s, student_id)]
    return ClassCheckInOut(day=day, school_day=school_day(day), subjects=[x for x in found if x is not None])


def log(s: Session, principal: Principal, *, student_id: UUID, body: ClassCheckInIn, now: datetime) -> ClassCheckInOut:
    """Record that class covered a chapter today. Her own tap: only the student makes it. Tapping the same chapter
    twice in a day records it once."""
    require_student_access(principal, student_id, SCOPE)
    if principal.role != "student":
        raise ApiError(403, "forbidden", "only the student says what her class covered")
    if body.subject_id not in {sid for sid, _ in _subjects(s, student_id)}:
        raise not_found("subject")
    tree = curriculum.subject_tree(s, body.subject_id)
    node = next((n for n in chapters(tree) if n.id == body.topic_id), None) if tree else None
    if node is None:
        raise ApiError(422, "not_a_chapter", "that is not one of this subject's chapters")
    day = local_date(now, identity.student_timezone(s, student_id))
    already = any(
        e.source == SOURCE and e.starts_on == day and body.topic_id in e.topic_ids
        for e in enrollment.list_teaching_entries(s, student_id=student_id)
        if e.subject_id == body.subject_id
    )
    if not already:
        enrollment.add_teaching_entry(
            s,
            tenant_id=principal.tenant_id,
            student_id=student_id,
            body=TeachingEntryIn(
                subject_id=body.subject_id,
                term="Class log",
                label=f"Class covered {node.code} {node.name}"[:300],
                starts_on=day,
                ends_on=day + timedelta(days=CURRENT_FOR_DAYS - 1),
                topic_ids=[body.topic_id],
                source=SOURCE,
            ),
        )
    return today(s, principal, student_id=student_id, now=now)
