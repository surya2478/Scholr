"""Master Router (ARCHITECTURE §7). Resolution order, stopping at the first confident result:
1. an open study test (all input belongs to it) → 2. subject/objective given by the UI or session (no LLM, AC-A1)
→ 3. keyword rules over the student's enrolled subjects → 4. `classifier` (Flash-Lite) → 5. ask the student.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.rbac import Principal, require_role
from app.llm.gateway import CallContext, LLMError, LLMGateway
from app.modules.assessment import service as assessment
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.routing import rules
from app.modules.routing.schemas import ClassifierOut, RouteChoice, RouteIn, RouteOut

SessionOpener = Callable[[], AbstractContextManager[Session]]
CLASSIFIER_ROLE = "classifier"
CLASSIFIER_PROMPT = "route_classify"
CLASSIFIER_THRESHOLD = 0.7
MAX_CHOICES = 3
NO_SUBJECT_INTENTS = frozenset({"wellbeing", "plan", "progress"})


def build_index(s: Session, subject_ids: list[UUID]) -> list[rules.IndexEntry]:
    index: list[rules.IndexEntry] = []
    for sid, subject in curriculum.subject_summaries(s, subject_ids).items():
        codes = curriculum.objectives_by_code(s, sid)
        aliases = rules.subject_aliases(subject.name, subject.code)
        for oid, obj in curriculum.objective_summaries(s, [oid for oid, _ in codes.values()]).items():
            index.append(
                rules.IndexEntry(
                    subject_id=sid,
                    subject_name=subject.name,
                    subject_aliases=aliases,
                    objective_id=oid,
                    objective_code=obj.code,
                    words=frozenset(rules.words(obj.statement)),
                    label=f"{subject.name} {obj.code} {obj.statement}",
                )
            )
    return index


def choices(candidates: list[rules.Candidate], subjects: dict[UUID, str]) -> list[RouteChoice]:
    seen: set[UUID] = set()
    out: list[RouteChoice] = []
    for c in candidates:
        if c.entry.objective_id in seen:
            continue
        seen.add(c.entry.objective_id)
        out.append(
            RouteChoice(
                subject_id=c.entry.subject_id,
                subject_name=c.entry.subject_name,
                objective_id=c.entry.objective_id,
                objective_code=c.entry.objective_code,
                label=c.entry.label,
            )
        )
        if len(out) == MAX_CHOICES:
            break
    return out or [
        RouteChoice(subject_id=sid, subject_name=name, objective_id=None, objective_code=None, label=name)
        for sid, name in subjects.items()
    ]


def _out(source: str, intent: str, confidence: float, **fields: object) -> RouteOut:
    base: dict[str, object] = {"subject_id": None, "subject_name": None, "objective_id": None, "objective_code": None}
    return RouteOut.model_validate({"source": source, "intent": intent, "confidence": confidence, **base, **fields})


def route(
    open_session: SessionOpener,
    gateway: Callable[[], LLMGateway],
    ctx: CallContext,
    principal: Principal,
    body: RouteIn,
) -> RouteOut:
    require_role(principal, "student")
    assert principal.student_id is not None
    intent = rules.intent_for(body.message)
    with open_session() as s:
        lock = assessment.active_exam_assessment(s, student_id=principal.student_id)
        if lock is not None:
            return _out("assessment_lock", "assessment", 1.0, assessment_id=lock)
        enrolled = [e.subject_id for e in enrollment.list_enrollments(s, [principal.student_id])]
        summaries = curriculum.subject_summaries(s, enrolled)
        subjects = {sid: sub.name for sid, sub in summaries.items()}
        subject_codes = {sid: sub.code for sid, sub in summaries.items()}
        if body.subject_id is not None:  # the UI or session already knows the subject: no LLM (AC-A1)
            if body.subject_id not in subjects:
                raise ApiError(422, "subject_not_enrolled", "that subject is not one of your subjects")
            objective = (
                curriculum.objective_summaries(s, [body.objective_id]).get(body.objective_id)
                if body.objective_id
                else None
            )
            return _out(
                "session",
                intent,
                1.0,
                subject_id=body.subject_id,
                subject_name=subjects[body.subject_id],
                objective_id=objective.id if objective else None,
                objective_code=objective.code if objective else None,
            )
        index = build_index(s, enrolled)

    if intent in NO_SUBJECT_INTENTS:
        return _out("rules", intent, 1.0)
    found = rules.match(body.message, index)
    if found.confident:  # the subject is clear; the objective only when it clearly beats the runner-up
        top = found.candidates[0]
        return _out(
            "rules",
            intent,
            min(1.0, 0.6 + 0.1 * top.score),
            subject_id=top.entry.subject_id,
            subject_name=top.entry.subject_name,
            objective_id=top.entry.objective_id if found.objective_confident else None,
            objective_code=top.entry.objective_code if found.objective_confident else None,
            choices=[] if found.objective_confident else choices(found.candidates, subjects),
        )

    try:
        result = gateway().structured(
            CLASSIFIER_ROLE,
            CLASSIFIER_PROMPT,
            {
                "message": body.message,
                "subjects": ", ".join(f"{code} ({subjects[sid]})" for sid, code in subject_codes.items()),
                "candidates": "\n".join(f"- {c.entry.label}" for c in found.candidates) or "(none)",
            },
            ClassifierOut,
            ctx,
        )
        classified: ClassifierOut | None = result.value
    except (LLMError, ApiError):  # no key configured or the call failed: ask instead
        classified = None

    if classified is not None and classified.confidence >= CLASSIFIER_THRESHOLD:
        sid = next((sid for sid, code in subject_codes.items() if code == classified.subject_code), None)
        entry = next(
            (
                e
                for e in index
                if sid is not None and e.subject_id == sid and e.objective_code == classified.objective_code
            ),
            None,
        )
        return _out(
            "classifier",
            classified.intent,
            classified.confidence,
            subject_id=sid,
            subject_name=subjects.get(sid) if sid else None,
            objective_id=entry.objective_id if entry else None,
            objective_code=entry.objective_code if entry else None,
        )
    return _out(
        "ask",
        classified.intent if classified else intent,
        classified.confidence if classified else 0.0,
        choices=choices(found.candidates, subjects),
    )
