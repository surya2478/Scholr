"""AC-S2/S3: high-severity input -> fixed response, incident, pending guardian notification; guardian reads audited."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.llm.gateway import CallContext
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.safety import service as safety
from app.modules.safety.models import SafetyIncident
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


def check(world: SimpleNamespace, gateway, text: str):  # noqa: ANN001, ANN201
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=world.student_user_id, role="student")
        return safety.check_input(
            s,
            gateway,
            CallContext(request_id="req-safety", tenant_id=world.tenant_id, student_id=world.student_id),
            tenant_id=world.tenant_id,
            student_id=world.student_id,
            text=text,
        )


def audit_actions(world: SimpleNamespace) -> list[str]:
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        return list(s.scalars(select(AuditLog.action).order_by(AuditLog.created_at)))


def test_high_severity_creates_incident_response_and_pending_notification(household_world: SimpleNamespace) -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply({"category": "self_harm", "severity": 3, "confidence": 0.95, "rationale": "intent"})
    outcome = check(household_world, gateway, "I want to kill myself")
    assert outcome.decision.action == "crisis_response" and outcome.blocks_tutoring
    assert outcome.response == safety.load_policy().responses["crisis_response"]
    assert outcome.incident_id is not None
    actions = audit_actions(household_world)
    assert "safety.incident_created" in actions and "safety.guardian_notification_pending" in actions


def test_classifier_failure_never_downgrades_a_rule_hit(household_world: SimpleNamespace) -> None:
    gateway, transport, _ = scripted_gateway()
    transport.fail("provider_error")
    outcome = check(household_world, gateway, "I want to kill myself")
    assert outcome.decision.action == "crisis_response"
    assert outcome.decision.classifier_failed


def test_academic_discussion_continues_and_unavailable_classifier_is_logged(household_world: SimpleNamespace) -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply({"category": "none", "severity": 0, "confidence": 0.9, "rationale": "academic"})
    outcome = check(household_world, gateway, "explain Durkheim's study of suicide rates")
    assert outcome.decision.action == "allow" and outcome.response is None and outcome.incident_id is None

    transport.fail("provider_error")
    outcome = check(household_world, gateway, "solve 3x - 12 = 2x + 45")
    assert outcome.decision.action == "allow"
    assert "safety.classifier_unavailable" in audit_actions(household_world)


def test_guardian_reads_incidents_with_audit_and_student_cannot(
    household_world: SimpleNamespace, auth_headers: Auth
) -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply({"category": "bullying", "severity": 2, "confidence": 0.8, "rationale": "bullying"})
    check(household_world, gateway, "I'm being bullied in the group chat every day")
    client = TestClient(create_app(session_factory=household_world.factory, gateway=gateway))

    assert client.get("/safety/incidents", headers=auth_headers("test|student")).status_code == 403
    parent = auth_headers("test|parent")
    [incident] = client.get("/safety/incidents", headers=parent).json()
    assert (incident["category"], incident["severity"], incident["escalation_status"]) == ("bullying", 2, "none")
    assert "safety.incidents_read" in audit_actions(household_world)

    updated = client.patch(
        f"/safety/incidents/{incident['id']}", headers=parent, json={"escalation_status": "resolved", "notes": "talked"}
    ).json()
    assert updated["escalation_status"] == "resolved" and updated["resolved_at"]
    with household_world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        assert s.scalar(select(SafetyIncident.notes)) == "talked"
