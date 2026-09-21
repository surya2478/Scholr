"""Mastery projection: learning events -> evidence -> rule v1 -> mastery_state.

Evidence is an ``attempt_evaluated`` event with status ``final``, or any evaluated attempt whose marks were
later replaced by an ``evaluation_overridden`` event (a human review; confidence 1.0). ``needs_review``
evaluations never move mastery (ARCHITECTURE §12). The table is a cache: ``rebuild`` recreates it from events.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.curriculum import service as curriculum
from app.modules.events import service as events
from app.modules.mastery import skills
from app.modules.mastery.models import MasteryState, SkillProfile
from app.modules.mastery.rules import (
    DEFAULT_CONFIG,
    LEVEL_NAMES,
    EvidenceItem,
    MasteryConfig,
    MasteryLevel,
    MasteryResult,
    compute_mastery,
)
from app.modules.mastery.schemas import EvidenceOut, MasteryOut, SkillOut
from app.modules.mistakes import service as mistakes
from app.modules.subjects import service as subjects

PROJECTED_TYPES = ("attempt_evaluated", "evaluation_overridden", "explanation_viewed")


@dataclass(frozen=True)
class Evidence:
    event_id: UUID
    evaluation_id: UUID
    attempt_id: UUID
    objective_ids: tuple[UUID, ...]
    item: EvidenceItem
    overridden: bool


def collect_evidence(event_views: Sequence[events.EventView]) -> list[Evidence]:
    """Pure: turn ordered events into mastery evidence. Later events for the same evaluation win."""
    evaluated: dict[UUID, tuple[events.EventView, events.AttemptEvaluated]] = {}
    overrides: dict[UUID, events.EvaluationOverridden] = {}
    for ev in event_views:
        if ev.type == "attempt_evaluated":
            payload = events.AttemptEvaluated.model_validate(ev.payload)
            evaluated[payload.evaluation_id] = (ev, payload)
        elif ev.type == "evaluation_overridden":
            override = events.EvaluationOverridden.model_validate(ev.payload)
            overrides[override.evaluation_id] = override

    evidence: list[Evidence] = []
    for evaluation_id, (ev, p) in evaluated.items():
        override = overrides.get(evaluation_id)
        if override is not None:
            score, confidence = override.marks_awarded / override.marks_available, 1.0
        elif p.status == "final":
            score, confidence = p.marks_awarded / p.marks_available, p.evaluation_confidence
        else:
            continue
        evidence.append(
            Evidence(
                event_id=ev.id,
                evaluation_id=evaluation_id,
                attempt_id=p.attempt_id,
                objective_ids=ev.objective_ids,
                item=EvidenceItem(
                    occurred_at=ev.occurred_at,
                    score=score,
                    help_level=p.help_level,
                    evaluation_confidence=confidence,
                    exam_style=p.exam_style,
                    stretch=p.stretch,
                    retention_check=p.retention_check,
                ),
                overridden=override is not None,
            )
        )
    evidence.sort(key=lambda e: e.item.occurred_at)
    return evidence


def _upsert(s: Session, tenant_id: UUID, student_id: UUID, objective_id: UUID, r: MasteryResult) -> None:
    values = {
        "level": int(r.level),
        "score": r.score,
        "mastery_confidence": r.mastery_confidence,
        "evidence_count": r.evidence_count,
        "independent_successes": r.independent_successes,
        "distinct_days": r.distinct_days,
        "last_demonstrated_at": r.last_demonstrated_at,
        "retention_risk": r.retention_risk,
        "rule_version": r.rule_version,
    }
    stmt = insert(MasteryState).values(tenant_id=tenant_id, student_id=student_id, objective_id=objective_id, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MasteryState.student_id, MasteryState.objective_id],
        set_={**{key: stmt.excluded[key] for key in values}, "updated_at": func.now()},
    )
    s.execute(stmt)


def recompute(
    s: Session,
    *,
    tenant_id: UUID,
    student_id: UUID,
    objective_ids: Sequence[UUID],
    now: datetime | None = None,
    config: MasteryConfig = DEFAULT_CONFIG,
) -> dict[UUID, MasteryResult]:
    now = now or datetime.now(UTC)
    wanted = list(dict.fromkeys(objective_ids))
    history = events.list_events(s, student_id=student_id, types=PROJECTED_TYPES, objective_ids=wanted)
    evidence = collect_evidence(history)
    explained = {oid for ev in history if ev.type == "explanation_viewed" for oid in ev.objective_ids}
    held = mistakes.open_high_severity_objectives(s, student_id, wanted)

    results: dict[UUID, MasteryResult] = {}
    for objective_id in wanted:
        items = [e.item for e in evidence if objective_id in e.objective_ids]
        if not items and objective_id not in explained:
            s.execute(
                delete(MasteryState).where(
                    MasteryState.student_id == student_id, MasteryState.objective_id == objective_id
                )
            )
            continue
        result = compute_mastery(
            items,
            now=now,
            explanation_viewed=objective_id in explained,
            has_open_high_severity_mistake=objective_id in held,
            config=config,
        )
        _upsert(s, tenant_id, student_id, objective_id, result)
        results[objective_id] = result
    return results


def recompute_skills(s: Session, *, tenant_id: UUID, student_id: UUID, subject_id: UUID) -> dict[str, float]:
    """Rebuild one subject's skill_profile rows from events (skill rule v1). Returns code -> score."""
    subject = curriculum.subject_summaries(s, [subject_id]).get(subject_id)
    if subject is None:
        return {}
    weights = subjects.taught_config_for(subject.code).skill_weights
    skill_ids = curriculum.skills_by_code(s, subject_id)
    history = [
        ev for ev in events.list_events(s, student_id=student_id, types=PROJECTED_TYPES) if ev.subject_id == subject_id
    ]
    overridden = {
        events.EvaluationOverridden.model_validate(ev.payload).evaluation_id
        for ev in history
        if ev.type == "evaluation_overridden"
    }
    evidence = []
    for ev in history:
        if ev.type != "attempt_evaluated":
            continue
        p = events.AttemptEvaluated.model_validate(ev.payload)
        # Reviewed marks replace the model's total, so its skill split no longer applies: only final ones count.
        if p.skill_marks and p.status == "final" and p.evaluation_id not in overridden:
            evidence.append(skills.SkillEvidence(p.marks_available, p.skill_marks))
    scores = skills.skill_scores(evidence, weights)
    s.execute(delete(SkillProfile).where(SkillProfile.student_id == student_id, SkillProfile.subject_id == subject_id))
    for code, result in scores.items():
        if code not in skill_ids:
            continue
        s.add(
            SkillProfile(
                tenant_id=tenant_id,
                student_id=student_id,
                skill_id=skill_ids[code][0],
                subject_id=subject_id,
                score=result.score,
                evidence_count=result.evidence_count,
                rule_version=skills.RULE_VERSION,
            )
        )
    s.flush()
    return {code: r.score for code, r in scores.items() if code in skill_ids}


def list_skills(s: Session, *, student_id: UUID, subject_id: UUID | None = None) -> list[SkillOut]:
    query = select(SkillProfile).where(SkillProfile.student_id == student_id)
    if subject_id is not None:
        query = query.where(SkillProfile.subject_id == subject_id)
    rows = s.scalars(query).all()
    names: dict[UUID, tuple[str, str]] = {}
    for sid in {r.subject_id for r in rows}:
        names.update({skill_id: (code, name) for code, (skill_id, name) in curriculum.skills_by_code(s, sid).items()})
    return sorted(
        (
            SkillOut(
                subject_id=r.subject_id,
                skill_code=names.get(r.skill_id, ("?", ""))[0],
                skill_name=names.get(r.skill_id, ("?", ""))[1],
                score=r.score,
                evidence_count=r.evidence_count,
                rule_version=r.rule_version,
            )
            for r in rows
        ),
        key=lambda x: (str(x.subject_id), x.skill_code),
    )


def project(
    s: Session, new_events: Sequence[events.EventView], *, tenant_id: UUID, now: datetime | None = None
) -> dict[UUID, MasteryResult]:
    """Synchronous projection hook: call right after appending events, in the same transaction."""
    touched: dict[UUID, list[UUID]] = defaultdict(list)
    skill_subjects: set[tuple[UUID, UUID]] = set()
    for ev in new_events:
        if ev.type in PROJECTED_TYPES:
            touched[ev.student_id].extend(ev.objective_ids)
        if ev.type in ("attempt_evaluated", "evaluation_overridden") and ev.subject_id is not None:
            skill_subjects.add((ev.student_id, ev.subject_id))
    results: dict[UUID, MasteryResult] = {}
    for student_id, objective_ids in touched.items():
        results.update(recompute(s, tenant_id=tenant_id, student_id=student_id, objective_ids=objective_ids, now=now))
    for student_id, subject_id in skill_subjects:
        recompute_skills(s, tenant_id=tenant_id, student_id=student_id, subject_id=subject_id)
    return results


def rebuild(s: Session, *, tenant_id: UUID, student_id: UUID, now: datetime | None = None) -> int:
    """Drop and recreate a student's mastery and skill rows from events. Returns mastery rows written."""
    history = events.list_events(s, student_id=student_id, types=PROJECTED_TYPES)
    objective_ids = list(dict.fromkeys(oid for ev in history for oid in ev.objective_ids))
    s.execute(delete(MasteryState).where(MasteryState.student_id == student_id))
    written = len(recompute(s, tenant_id=tenant_id, student_id=student_id, objective_ids=objective_ids, now=now))
    for subject_id in {ev.subject_id for ev in history if ev.subject_id is not None}:
        recompute_skills(s, tenant_id=tenant_id, student_id=student_id, subject_id=subject_id)
    return written


def list_mastery(s: Session, *, student_id: UUID, subject_id: UUID | None = None) -> list[MasteryOut]:
    rows = s.scalars(select(MasteryState).where(MasteryState.student_id == student_id)).all()
    objectives = curriculum.objective_summaries(s, [r.objective_id for r in rows])
    out = [
        MasteryOut(
            objective_id=r.objective_id,
            objective_code=objectives[r.objective_id].code,
            objective_statement=objectives[r.objective_id].statement,
            subject_id=objectives[r.objective_id].subject_id,
            level=r.level,
            level_name=LEVEL_NAMES[r.level],
            score=r.score,
            mastery_confidence=r.mastery_confidence,
            evidence_count=r.evidence_count,
            independent_successes=r.independent_successes,
            distinct_days=r.distinct_days,
            last_demonstrated_at=r.last_demonstrated_at,
            retention_risk=r.retention_risk,
            rule_version=r.rule_version,
        )
        for r in rows
        if r.objective_id in objectives and (subject_id is None or objectives[r.objective_id].subject_id == subject_id)
    ]
    return sorted(out, key=lambda m: curriculum.code_sort_key(m.objective_code))


def evidence_for(s: Session, *, student_id: UUID, objective_id: UUID) -> list[EvidenceOut]:
    history = events.list_events(s, student_id=student_id, types=PROJECTED_TYPES, objective_ids=[objective_id])
    return [
        EvidenceOut(
            event_id=e.event_id,
            evaluation_id=e.evaluation_id,
            attempt_id=e.attempt_id,
            occurred_at=e.item.occurred_at,
            score=round(e.item.score, 4),
            help_level=e.item.help_level,
            evaluation_confidence=e.item.evaluation_confidence,
            exam_style=e.item.exam_style,
            stretch=e.item.stretch,
            retention_check=e.item.retention_check,
            overridden=e.overridden,
        )
        for e in collect_evidence(history)
    ]


def secure_counts_at(
    s: Session, *, student_id: UUID, moments: Sequence[datetime], config: MasteryConfig = DEFAULT_CONFIG
) -> list[int]:
    """Objectives at Competent or above at each moment, replayed from events. Writes nothing.

    Used for the guardian's weekly trend. Mistake holds are not replayed (the mistake bank is itself a projection
    of the same events, and only its current state is stored), so a past week can read a little high.
    """
    history = events.list_events(s, student_id=student_id, types=PROJECTED_TYPES)
    counts = []
    for moment in moments:
        so_far = [ev for ev in history if ev.occurred_at <= moment]
        evidence = collect_evidence(so_far)
        explained = {oid for ev in so_far if ev.type == "explanation_viewed" for oid in ev.objective_ids}
        secure = 0
        for objective_id in dict.fromkeys(oid for ev in so_far for oid in ev.objective_ids):
            items = [e.item for e in evidence if objective_id in e.objective_ids]
            if not items and objective_id not in explained:
                continue
            result = compute_mastery(
                items,
                now=moment,
                explanation_viewed=objective_id in explained,
                has_open_high_severity_mistake=False,
                config=config,
            )
            secure += result.level >= MasteryLevel.COMPETENT
        counts.append(secure)
    return counts
