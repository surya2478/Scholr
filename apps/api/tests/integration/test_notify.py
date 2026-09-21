"""Guardian notification delivery for high-severity incidents (AC-S3), with a fake channel."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.db import set_rls_context
from app.modules.audit.models import AuditLog
from app.modules.safety.models import SafetyIncident
from app.modules.safety.notify import Alert, deliver_pending

pytestmark = pytest.mark.db


class FakeChannel:
    name = "fake"

    def __init__(self, ok: bool) -> None:
        self.ok, self.sent = ok, []

    def send(self, alert: Alert) -> bool:
        self.sent.append(alert)
        return self.ok


def test_high_severity_incidents_are_delivered_once(household_world: SimpleNamespace) -> None:
    w = household_world
    now = datetime.now(UTC)

    def incident(severity: int) -> SafetyIncident:
        return SafetyIncident(
            tenant_id=w.tenant_id,
            student_id=w.student_id,
            occurred_at=now,
            category="self_harm",
            severity=severity,
            rule_ids=["test"],
            action_taken="crisis_response",
            policy_version="safety_v2",
            classifier_output={},
        )

    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        high, medium = incident(3), incident(2)
        s.add_all([high, medium])
        s.flush()
        high_id = high.id

        failing = FakeChannel(ok=False)
        assert deliver_pending(s, failing, now=now).failed == 1  # retried next time
        assert s.get(SafetyIncident, high_id).notified_at is None

        channel = FakeChannel(ok=True)
        report = deliver_pending(s, channel, now=now)
        assert (report.delivered, [a.incident_id for a in channel.sent]) == (1, [high_id])  # medium is not pushed
        assert s.get(SafetyIncident, high_id).escalation_status == "notified"
        assert "Test Student" not in str(channel.sent[0].payload())  # no names or message text leave the app
        assert deliver_pending(s, channel, now=now).delivered == 0
        actions = set(s.scalars(select(AuditLog.action).where(AuditLog.entity_id == high_id)))
        assert {"safety.guardian_notified", "safety.guardian_notification_failed"} <= actions
