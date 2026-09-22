"""Evaluation orchestration: load inputs (transaction 1), run the subject's pipeline (no transaction held during
the LLM call), then persist the evaluation, emit events and update projections (transaction 2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_role, require_student_access
from app.llm.gateway import CallContext, LLMGateway
from app.modules.assessment import service as assessment
from app.modules.assessment.schemas import ExaminerInsightsOut
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.evaluation import essay_levels, structured_math
from app.modules.evaluation.models import Evaluation
from app.modules.evaluation.schemas import (
    AnswerCheckOut,
    AutopsyEntryOut,
    AutopsyIn,
    AwardOut,
    EvaluationOut,
    FeedbackOut,
    MistakeNoteOut,
    OverrideIn,
    ReviewItemOut,
)
from app.modules.events import service as events
from app.modules.mastery import service as mastery
from app.modules.mistakes import service as mistakes
from app.modules.subjects import service as subjects


@dataclass(frozen=True)
class PreparedEvaluation:
    attempt: assessment.AttemptView
    math: structured_math.MathInput | None = None
    essay: essay_levels.EssayInput | None = None


Outcome = structured_math.MathOutcome | essay_levels.EssayOutcome


def latest_row(s: Session, attempt_id: UUID) -> Evaluation | None:
    return s.scalar(
        select(Evaluation).where(Evaluation.attempt_id == attempt_id).order_by(Evaluation.created_at.desc()).limit(1)
    )


def needs_review_count(s: Session, *, student_id: UUID) -> int:
    return (
        s.scalar(
            select(func.count(Evaluation.id)).where(
                Evaluation.student_id == student_id, Evaluation.status == "needs_review"
            )
        )
        or 0
    )


def marks_for_attempts(s: Session, attempt_ids: Sequence[UUID]) -> dict[UUID, assessment.ItemMark]:
    """attempt_id -> its latest evaluation's marks (for assessment scoring)."""
    if not attempt_ids:
        return {}
    rows = s.scalars(
        select(Evaluation).where(Evaluation.attempt_id.in_(list(attempt_ids))).order_by(Evaluation.created_at)
    ).all()
    return {r.attempt_id: assessment.ItemMark(r.id, r.status, r.marks_awarded) for r in rows}  # later rows win


@dataclass(frozen=True)
class EvaluationSummary:
    evaluation_id: UUID
    status: str
    marks_awarded: float
    marks_available: float
    mistake_descriptions: tuple[str, ...]


def evaluation_summaries_for_attempts(s: Session, attempt_ids: Sequence[UUID]) -> dict[UUID, EvaluationSummary]:
    """attempt_id -> summary with marks and diagnosed mistakes (latest evaluation wins)."""
    if not attempt_ids:
        return {}
    rows = s.scalars(
        select(Evaluation).where(Evaluation.attempt_id.in_(list(attempt_ids))).order_by(Evaluation.created_at)
    ).all()
    out: dict[UUID, EvaluationSummary] = {}
    for r in rows:
        mistakes = tuple(m.get("description", "") for m in (r.diagnosed_mistakes or []) if m.get("description"))
        out[r.attempt_id] = EvaluationSummary(
            evaluation_id=r.id,
            status=r.status,
            marks_awarded=r.marks_awarded,
            marks_available=r.marks_available,
            mistake_descriptions=mistakes,
        )
    return out


def latest_id_for_attempt(s: Session, attempt_id: UUID) -> UUID | None:
    row = latest_row(s, attempt_id)
    return row.id if row else None


def to_out(row: Evaluation) -> EvaluationOut:
    feedback = row.feedback or {}
    check = (row.tool_results or {}).get("final_answer")
    return EvaluationOut(
        id=row.id,
        attempt_id=row.attempt_id,
        status=row.status,
        provisional=row.status == "needs_review",
        marks_awarded=row.marks_awarded,
        marks_available=row.marks_available,
        feedback=FeedbackOut(
            summary=feedback.get("summary", ""),
            what_went_well=feedback.get("what_went_well"),
            next_step=feedback.get("next_step") or structured_math.DEFAULT_NEXT_STEP,
            autopsy=feedback.get("autopsy"),
        ),
        final_answer_check=AnswerCheckOut(status=check["status"], detail=check["detail"]) if check else None,
        awards=[AwardOut(**a) for a in (row.criterion_scores or {}).get("awards", [])],
        mistakes=[
            MistakeNoteOut(
                category=m["category"], label=m["label"], severity=m["severity"], description=m["description"]
            )
            for m in row.diagnosed_mistakes or []
        ],
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def prepare(s: Session, principal: Principal, attempt_id: UUID) -> PreparedEvaluation | EvaluationOut:
    require_role(principal, "student", "admin")
    attempt = assessment.get_attempt(s, principal, attempt_id)
    existing = latest_row(s, attempt.id)
    if existing is not None:
        return to_out(existing)
    if attempt.assessment_kind in assessment.EXAM_STYLE_KINDS and attempt.assessment_status not in (
        "submitted",
        "evaluated",
    ):
        raise ApiError(409, "assessment_not_submitted", "Test answers are marked after you submit the test.")
    if not attempt.ready_for_marking:
        raise ApiError(
            409, "transcription_not_confirmed", "Check and confirm the transcription of your photo before it is marked."
        )
    subject = curriculum.subject_summaries(s, [attempt.item.subject_id])[attempt.item.subject_id]
    config = subjects.taught_config_for(subject.code)
    item = attempt.item
    if config.evaluation.pipeline == essay_levels.PIPELINE:
        answer = "\n".join(x for x in (attempt.working_for_marking, attempt.final_answer) if x and x.strip())
        essay = essay_levels.EssayInput(
            marks=item.marks,
            stem=item.stem,
            context=item.context,
            command_word=item.command_word,
            mark_scheme=str((item.mark_scheme or {}).get("text", "")),
            answer=answer,
            evaluator_role=config.evaluation.evaluator_role,
            second_evaluator_role=config.evaluation.second_evaluator_role,
            dual_marking=config.evaluation.dual_marking,
            max_disagreement=dict(config.evaluation.max_disagreement),
            confidence_threshold=config.evaluation.confidence_threshold,
            calibrated=config.evaluation.calibrated,
            level_guide=dict(config.evaluation.level_guide),
            mistake_categories=tuple(config.mistake_categories),
            mistake_labels=tuple(config.common_mistakes),
        )
        return PreparedEvaluation(attempt=attempt, essay=essay)
    if config.evaluation.pipeline != structured_math.PIPELINE:
        raise ApiError(501, "pipeline_not_available", f"Marking for {subject.name} is not available yet.")
    math = structured_math.MathInput(
        marks=item.marks,
        stem=item.stem,
        context=item.context,
        command_word=item.command_word,
        answer_spec=dict(item.answer_spec),
        mark_scheme=str((item.mark_scheme or {}).get("text", "")),
        working=attempt.working_for_marking,
        final_answer=attempt.final_answer,
        from_photo=bool(attempt.photo_uris),
        evaluator_role=config.evaluation.evaluator_role,
        confidence_threshold=config.evaluation.confidence_threshold,
        mistake_categories=tuple(config.mistake_categories),
        mistake_labels=tuple(config.common_mistakes),
    )
    return PreparedEvaluation(attempt=attempt, math=math)


def run(gateway: LLMGateway, ctx: CallContext, prepared: PreparedEvaluation) -> Outcome:
    if prepared.essay is not None:
        return essay_levels.evaluate(gateway, ctx, prepared.essay)
    assert prepared.math is not None
    return structured_math.evaluate(gateway, ctx, prepared.math)


def record(
    s: Session,
    principal: Principal,
    prepared: PreparedEvaluation,
    outcome: Outcome,
    *,
    now: datetime,
) -> EvaluationOut:
    attempt = prepared.attempt
    existing = latest_row(s, attempt.id)  # a concurrent request may have finished first
    if existing is not None:
        return to_out(existing)

    row = Evaluation(
        tenant_id=attempt.tenant_id,
        student_id=attempt.student_id,
        attempt_id=attempt.id,
        pipeline=outcome.pipeline,
        pipeline_version=outcome.pipeline_version,
        rubric_version=outcome.rubric_version,
        marks_awarded=outcome.marks_awarded,
        marks_available=outcome.marks_available,
        criterion_scores=outcome.criterion_scores,
        level_band=outcome.level,
        feedback={**outcome.feedback, "provisional": outcome.status != "final"},
        diagnosed_mistakes=outcome.mistakes,
        tool_results=outcome.tool_results,
        confidence=outcome.confidence,
        agreement=outcome.agreement_record,
        status=outcome.status,
    )
    s.add(row)
    s.flush()

    item = attempt.item
    if not item.objective_ids:  # untagged item: feedback only, no mastery evidence
        return to_out(row)
    common = {
        "tenant_id": attempt.tenant_id,
        "student_id": attempt.student_id,
        "occurred_at": now,
        "subject_id": item.subject_id,
        "objective_ids": list(item.objective_ids),
        "ref_type": "evaluation",
        "ref_id": row.id,
    }
    new_events = [
        events.append(
            s,
            event_type="attempt_evaluated",
            payload={
                "attempt_id": attempt.id,
                "evaluation_id": row.id,
                "marks_awarded": outcome.marks_awarded,
                "marks_available": outcome.marks_available,
                "help_level": attempt.max_assistance_level,
                "evaluation_confidence": outcome.confidence,
                "status": outcome.status,
                "exam_style": attempt.assessment_kind in assessment.EXAM_STYLE_KINDS,
                "stretch": item.difficulty == 5,
                "retention_check": attempt.assessment_kind == "retention",
                "skill_marks": outcome.skill_marks,
            },
            **common,
        )
    ]
    descriptions: dict[tuple[UUID, str], str] = {}
    if outcome.status == "final":  # provisional diagnoses never enter the mistake bank
        for mistake in outcome.mistakes:
            new_events.append(
                events.append(
                    s,
                    event_type="mistake_diagnosed",
                    payload={
                        "evaluation_id": row.id,
                        "attempt_id": attempt.id,
                        "mistake_type": mistake["category"],
                        "severity": mistake["severity"],
                        "fingerprint": mistake["fingerprint"],
                    },
                    **common,
                )
            )
            descriptions[(row.id, mistake["fingerprint"])] = mistake["description"]
    mistakes.project(s, new_events, tenant_id=attempt.tenant_id, descriptions=descriptions)
    mastery.project(s, new_events, tenant_id=attempt.tenant_id, now=now)
    return to_out(row)


def get_evaluation(s: Session, principal: Principal, evaluation_id: UUID) -> EvaluationOut:
    row = s.get(Evaluation, evaluation_id)
    if row is None:
        raise not_found("evaluation")
    require_student_access(principal, row.student_id, "assessments")
    return to_out(row)


def examiner_insights(s: Session, principal: Principal, evaluation_id: UUID) -> ExaminerInsightsOut:
    """What the examiner report says about the question this evaluation marked (AC-R6).

    Reached only through an evaluation, so it cannot be read before the answer is marked: the reports name the
    answers that scored. A timed paper is marked only once it is submitted, so nothing leaks mid-sitting either.
    """
    row = s.get(Evaluation, evaluation_id)
    if row is None:
        raise not_found("evaluation")
    require_student_access(principal, row.student_id, "assessments")
    attempt = assessment.get_attempt(s, principal, row.attempt_id)
    return assessment.examiner_insights(s, attempt.item.id)


def review_queue(s: Session, principal: Principal, *, student_id: UUID) -> list[ReviewItemOut]:
    """Provisional evaluations, oldest first. Reviewers see the mark scheme, so students are never reviewers."""
    require_role(principal, "guardian", "admin")
    require_student_access(principal, student_id, "assessments")
    rows = s.scalars(
        select(Evaluation)
        .where(Evaluation.student_id == student_id, Evaluation.status == "needs_review")
        .order_by(Evaluation.created_at)
    ).all()
    queue = []
    for row in rows:
        attempt = assessment.get_attempt(s, principal, row.attempt_id)
        item = attempt.item
        queue.append(
            ReviewItemOut(
                evaluation=to_out(row),
                student_id=row.student_id,
                subject_id=item.subject_id,
                source_ref=item.source_ref,
                context=item.context,
                stem=item.stem,
                working=attempt.working_for_marking,
                final_answer=attempt.final_answer,
                mark_scheme=str(item.mark_scheme.get("text", "")),
                confidence=row.confidence,
                issues=[str(issue) for issue in (row.agreement or {}).get("issues", [])],
            )
        )
    return queue


def override(
    s: Session, principal: Principal, evaluation_id: UUID, body: OverrideIn, *, now: datetime
) -> EvaluationOut:
    """A human sets the marks. The override becomes mastery evidence (confidence 1.0) and is audited."""
    require_role(principal, "guardian", "admin")
    row = s.get(Evaluation, evaluation_id)
    if row is None:
        raise not_found("evaluation")
    require_student_access(principal, row.student_id, "assessments")
    if row.status == "overridden":
        raise ApiError(409, "already_overridden", "this evaluation has already been reviewed")
    if body.marks_awarded > row.marks_available:
        raise ApiError(422, "marks_out_of_range", f"marks must be between 0 and {row.marks_available:g}")

    previous = {"status": row.status, "marks_awarded": row.marks_awarded}
    row.marks_awarded = body.marks_awarded
    row.status = "overridden"
    row.reviewed_by = principal.user_id
    row.reviewed_at = now
    row.feedback = {**(row.feedback or {}), "provisional": False}
    row.agreement = {**(row.agreement or {}), "override": {**previous, "note": body.note}}
    s.flush()

    attempt = assessment.get_attempt(s, principal, row.attempt_id)
    if attempt.item.objective_ids:  # untagged items never produce mastery evidence
        event = events.append(
            s,
            tenant_id=row.tenant_id,
            student_id=row.student_id,
            event_type="evaluation_overridden",
            occurred_at=now,
            subject_id=attempt.item.subject_id,
            objective_ids=list(attempt.item.objective_ids),
            payload={
                "attempt_id": attempt.id,
                "evaluation_id": row.id,
                "reviewer_user_id": principal.user_id,
                "marks_awarded": body.marks_awarded,
                "marks_available": row.marks_available,
            },
            ref_type="evaluation",
            ref_id=row.id,
        )
        mastery.project(s, [event], tenant_id=row.tenant_id, now=now)
    audit.record(
        s,
        tenant_id=row.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="evaluation.overridden",
        entity_type="evaluation",
        entity_id=row.id,
        student_id=row.student_id,
        meta={
            "previous_status": previous["status"],
            "previous_marks": previous["marks_awarded"],
            "marks_awarded": body.marks_awarded,
        },
    )
    return to_out(row)


def record_autopsy(
    s: Session, principal: Principal, evaluation_id: UUID, body: AutopsyIn, *, now: datetime
) -> EvaluationOut:
    require_role(principal, "student", "guardian", "admin")
    row = s.get(Evaluation, evaluation_id)
    if row is None:
        raise not_found("evaluation")
    require_student_access(principal, row.student_id, "assessments")
    autopsy_data = {
        "category": body.category,
        "takeaway": body.takeaway,
        "recorded_at": now.isoformat(),
    }
    row.feedback = {**(row.feedback or {}), "autopsy": autopsy_data}
    s.flush()
    return to_out(row)


def list_autopsies(
    s: Session, principal: Principal, *, student_id: UUID, subject_id: UUID | None = None
) -> list[AutopsyEntryOut]:
    require_student_access(principal, student_id, "assessments")
    rows = s.scalars(
        select(Evaluation)
        .where(Evaluation.student_id == student_id)
        .order_by(Evaluation.created_at.desc())
    ).all()
    entries: list[AutopsyEntryOut] = []
    for r in rows:
        fb = r.feedback or {}
        autopsy = fb.get("autopsy")
        if not isinstance(autopsy, dict) or not autopsy.get("takeaway"):
            continue
        attempt = assessment.get_attempt(s, principal, r.attempt_id)
        item = attempt.item
        if subject_id is not None and item.subject_id != subject_id:
            continue
        obj_code = None
        if item.objective_ids:
            summaries = curriculum.objective_summaries(s, [item.objective_ids[0]])
            if item.objective_ids[0] in summaries:
                obj_code = summaries[item.objective_ids[0]].code
        recorded_at_str = autopsy.get("recorded_at")
        try:
            rec_dt = datetime.fromisoformat(recorded_at_str) if recorded_at_str else r.created_at
        except Exception:
            rec_dt = r.created_at

        entries.append(
            AutopsyEntryOut(
                evaluation_id=r.id,
                attempt_id=r.attempt_id,
                subject_id=item.subject_id,
                objective_code=obj_code,
                stem=item.stem,
                category=str(autopsy.get("category", "conceptual")),
                takeaway=str(autopsy.get("takeaway", "")),
                marks_awarded=r.marks_awarded,
                marks_available=r.marks_available,
                recorded_at=rec_dt,
            )
        )
    return entries
