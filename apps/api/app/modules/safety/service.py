"""Safety pipeline (ARCHITECTURE §17): rules -> classifier -> policy table -> incident + audit.

Runs on every student message before any tutoring. Responses are fixed templates from policy.yaml, never generated.
Failure behaviour: classifier unavailable -> the rule severity stands (never downgraded); no rule hit -> the academic
flow continues and `classifier_unavailable` is recorded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.core.rbac import Principal, require_role, require_student_access
from app.llm.gateway import CallContext, LLMError, LLMGateway
from app.modules.audit import service as audit
from app.modules.safety.models import SafetyIncident
from app.modules.safety.rules import ClassifierResult, SafetyDecision, Severity, decide, evaluate_rules
from app.modules.safety.schemas import ClassifierOutput, IncidentOut, IncidentUpdate, SafetyPolicyFile

POLICY_FILE = Path(__file__).with_name("policy.yaml")
CLASSIFIER_ROLE = "safety_classifier"
CLASSIFIER_PROMPT = "safety_classifier"


@lru_cache
def load_policy(path: Path = POLICY_FILE) -> SafetyPolicyFile:
    return SafetyPolicyFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def response_for(decision: SafetyDecision, policy: SafetyPolicyFile | None = None) -> str | None:
    """Fixed response for a blocking decision; None when the academic flow continues."""
    if decision.action == "allow":
        return None
    policy = policy or load_policy()
    key = (
        "personal_info"
        if decision.category == "personal_info" and decision.action == "supportive_response"
        else (decision.action)
    )
    text = policy.responses[key]
    if decision.action == "crisis_response" and policy.crisis_resources.verified:
        lines = [f"- {r.name}: {r.contact} ({r.region})" for r in policy.crisis_resources.entries]
        if lines:
            text = text + "\n\n" + "\n".join(lines)
    return text


def classify(gateway: LLMGateway, ctx: CallContext, text: str, context: str = "") -> ClassifierResult | None:
    """Advisory classification; None if the classifier is unavailable (the caller keeps rule severity)."""
    try:
        result = gateway.structured(
            CLASSIFIER_ROLE, CLASSIFIER_PROMPT, {"message": text, "context": context}, ClassifierOutput, ctx
        )
    except LLMError:
        return None
    out = result.value
    category = None if out.category == "none" else out.category
    return ClassifierResult(category=category, severity=Severity(out.severity), confidence=out.confidence)


@dataclass(frozen=True)
class SafetyOutcome:
    decision: SafetyDecision
    response: str | None
    incident_id: UUID | None

    @property
    def blocks_tutoring(self) -> bool:
        return self.decision.action != "allow"


def check_input(
    s: Session,
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    tenant_id: UUID,
    student_id: UUID,
    text: str,
    context: str = "",
    message_id: UUID | None = None,
    now: datetime | None = None,
) -> SafetyOutcome:
    now = now or datetime.now(UTC)
    hits = evaluate_rules(text)
    classifier = classify(gateway, ctx, text, context)
    decision = decide(hits, classifier, classifier_failed=classifier is None)
    incident_id: UUID | None = None
    if decision.create_incident and decision.category is not None:
        incident = SafetyIncident(
            tenant_id=tenant_id,
            student_id=student_id,
            message_id=message_id,
            occurred_at=now,
            category=decision.category,
            severity=int(decision.severity),
            rule_ids=list(decision.rule_ids),
            classifier_output=(
                {"used": decision.classifier_used, "failed": decision.classifier_failed}
                | (
                    {
                        "category": classifier.category,
                        "severity": int(classifier.severity),
                        "confidence": classifier.confidence,
                    }
                    if classifier
                    else {}
                )
            ),
            policy_version=decision.policy_version,
            action_taken=decision.action,
        )
        s.add(incident)
        s.flush()
        incident_id = incident.id
        audit.record(
            s,
            tenant_id=tenant_id,
            actor_user_id=None,
            actor_role="system",
            action="safety.incident_created",
            entity_type="safety_incident",
            entity_id=incident.id,
            student_id=student_id,
            meta={
                "category": decision.category,
                "severity": int(decision.severity),
                "action": decision.action,
                "rule_ids": list(decision.rule_ids),
                "policy_version": decision.policy_version,
            },
        )
        if decision.notify_guardian_now:
            # CONTEXT U4: the notification channel is not chosen yet. The pending notification is recorded so the
            # parent dashboard shows it immediately; a sender delivers it once the channel exists.
            audit.record(
                s,
                tenant_id=tenant_id,
                actor_user_id=None,
                actor_role="system",
                action="safety.guardian_notification_pending",
                entity_type="safety_incident",
                entity_id=incident.id,
                student_id=student_id,
                meta={"category": decision.category, "severity": int(decision.severity)},
            )
    elif classifier is None and not hits:
        audit.record(
            s,
            tenant_id=tenant_id,
            actor_user_id=None,
            actor_role="system",
            action="safety.classifier_unavailable",
            entity_type="student",
            entity_id=student_id,
            student_id=student_id,
        )
    return SafetyOutcome(decision=decision, response=response_for(decision), incident_id=incident_id)


# Deterministic checks on tutor output (ARCHITECTURE §17 "output -> checks").
_OUTPUT_RULES = (
    ("claims_human", re.compile(r"\b(?:i\s+am|i'm)\s+(?:a\s+)?(?:real\s+)?(?:human|person|teacher)\b", re.IGNORECASE)),
    (
        "asks_personal_data",
        re.compile(
            r"\b(?:what\s+is|tell\s+me|send\s+me|share)\s+your\s+(?:home\s+)?(?:address|phone|number|photo|"
            r"picture|full\s+name|school\s+name|location|password)\b",
            re.IGNORECASE,
        ),
    ),
    ("arranges_contact", re.compile(r"\b(?:meet\s+(?:me|up)|add\s+me\s+on|message\s+me\s+on)\b", re.IGNORECASE)),
)


def output_issues(text: str) -> list[str]:
    return [name for name, pattern in _OUTPUT_RULES if pattern.search(text)]


# ---------------------------------------------------------------------------
# Incidents (guardian / admin)
# ---------------------------------------------------------------------------


def _out(row: SafetyIncident) -> IncidentOut:
    return IncidentOut(
        id=row.id,
        student_id=row.student_id,
        occurred_at=row.occurred_at,
        category=row.category,
        severity=row.severity,
        action_taken=row.action_taken,
        rule_ids=list(row.rule_ids or []),
        policy_version=row.policy_version,
        escalation_status=row.escalation_status,
        notified_at=row.notified_at,
        resolved_at=row.resolved_at,
        notes=row.notes,
    )


def list_incidents(
    s: Session, principal: Principal, *, student_id: UUID, status: str | None = None
) -> list[IncidentOut]:
    require_role(principal, "guardian", "admin")
    require_student_access(principal, student_id, "safety")
    query = select(SafetyIncident).where(SafetyIncident.student_id == student_id)
    if status is not None:
        query = query.where(SafetyIncident.escalation_status == status)
    rows = s.scalars(query.order_by(SafetyIncident.occurred_at.desc())).all()
    audit.record(  # AC-S2: every guardian/admin read of safety data is audited
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action="safety.incidents_read",
        entity_type="student",
        entity_id=student_id,
        student_id=student_id,
        meta={"count": len(rows)},
    )
    return [_out(r) for r in rows]


def update_incident(s: Session, principal: Principal, incident_id: UUID, body: IncidentUpdate) -> IncidentOut:
    require_role(principal, "guardian", "admin")
    row = s.get(SafetyIncident, incident_id)
    if row is None:
        raise not_found("incident")
    require_student_access(principal, row.student_id, "safety")
    if row.escalation_status == "resolved":
        raise ApiError(409, "already_resolved", "this incident is already resolved")
    now = datetime.now(UTC)
    row.escalation_status = body.escalation_status
    if body.notes is not None:
        row.notes = body.notes
    if body.escalation_status == "resolved":
        row.resolved_at = now
    s.flush()
    audit.record(
        s,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        action=f"safety.incident_{body.escalation_status}",
        entity_type="safety_incident",
        entity_id=row.id,
        student_id=row.student_id,
    )
    return _out(row)
