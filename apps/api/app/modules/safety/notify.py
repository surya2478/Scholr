"""Guardian notification for high-severity safety incidents (ARCHITECTURE §17, AC-S3).

Incidents are never delivered from the request path: `app.jobs.notify` polls for pending incidents (severity high,
not yet notified) and hands each to a channel. The notification carries no message text and no names — only that an
alert needs attention, its category, severity and time — so the parent opens the app to see it.

Channels: `LogChannel` (default until the parent chooses a channel, CONTEXT U4: the alert is visible in-app on the
parent overview and recorded in the audit log) and `WebhookChannel` (an HTTPS endpoint, e.g. an email/SMS/WhatsApp
relay the family sets up). A failed delivery is retried on the next poll.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit import service as audit
from app.modules.safety.models import SafetyIncident

NOTIFY_SEVERITY = 3  # high: pre-written response + immediate guardian notification


@dataclass(frozen=True)
class Alert:
    incident_id: UUID
    tenant_id: UUID
    student_id: UUID
    category: str
    severity: int
    occurred_at: datetime

    def payload(self) -> dict[str, str | int]:
        return {
            "type": "scholr.safety_alert",
            "incident_id": str(self.incident_id),
            "category": self.category,
            "severity": self.severity,
            "occurred_at": self.occurred_at.isoformat(),
            "open": "/parent/safety",
        }


class Channel(Protocol):
    name: str

    def send(self, alert: Alert) -> bool: ...


class LogChannel:
    """Delivery = visible in the parent app (overview + safety page) and recorded in the audit log."""

    name = "in_app"

    def send(self, alert: Alert) -> bool:
        return True


class WebhookChannel:
    name = "webhook"

    def __init__(self, url: str, timeout_s: float = 10.0) -> None:
        if not url.startswith("https://"):
            raise ValueError("notification webhook must use https")
        self.url, self.timeout_s = url, timeout_s

    def send(self, alert: Alert) -> bool:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(alert.payload()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310 (https enforced)
                return 200 <= response.status < 300
        except OSError:
            return False


def pending_alerts(s: Session, *, limit: int = 50) -> list[Alert]:
    rows = s.scalars(
        select(SafetyIncident)
        .where(
            SafetyIncident.severity >= NOTIFY_SEVERITY,
            SafetyIncident.notified_at.is_(None),
            SafetyIncident.escalation_status == "none",
        )
        .order_by(SafetyIncident.occurred_at)
        .limit(limit)
    )
    return [Alert(r.id, r.tenant_id, r.student_id, r.category, r.severity, r.occurred_at) for r in rows]


@dataclass(frozen=True)
class DeliveryReport:
    delivered: int
    failed: int


def deliver_pending(s: Session, channel: Channel, *, now: datetime) -> DeliveryReport:
    delivered = failed = 0
    for alert in pending_alerts(s):
        ok = channel.send(alert)
        audit.record(
            s,
            tenant_id=alert.tenant_id,
            actor_user_id=None,
            actor_role="system",
            action="safety.guardian_notified" if ok else "safety.guardian_notification_failed",
            entity_type="safety_incident",
            entity_id=alert.incident_id,
            student_id=alert.student_id,
            meta={"channel": channel.name, "severity": alert.severity},
        )
        if not ok:
            failed += 1
            continue
        row = s.get(SafetyIncident, alert.incident_id)
        if row is not None:
            row.notified_at = now
            row.escalation_status = "notified"
        delivered += 1
    s.flush()
    return DeliveryReport(delivered, failed)
