"""Consent records (guardian consent, student assent), withdrawal audit, and the admin-only audit log."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.audit.models import AuditLog

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


def test_consent_lifecycle_and_audit_access(household_world: SimpleNamespace, auth_headers: Auth) -> None:
    w = household_world
    client = TestClient(create_app(session_factory=w.factory))
    student, parent = auth_headers("test|student"), auth_headers("test|parent")

    given = client.post("/consents", headers=parent, json={})
    assert given.status_code == 201, given.text
    assert given.json()["kind"] == "guardian_consent"
    assert client.post("/consents", headers=parent, json={}).json()["id"] == given.json()["id"]  # idempotent
    assent = client.post("/consents", headers=student, json={}).json()
    assert assent["kind"] == "student_assent"
    bad = client.post("/consents", headers=student, json={"policy_version": "old"})
    assert bad.json()["error"]["code"] == "unknown_policy_version"

    assert {c["kind"] for c in client.get("/consents", headers=student).json()} == {
        "guardian_consent",
        "student_assent",
    }
    assert client.post(f"/consents/{given.json()['id']}/withdraw", headers=student).status_code == 403
    withdrawn = client.post(f"/consents/{given.json()['id']}/withdraw", headers=parent).json()
    assert withdrawn["withdrawn_at"] is not None

    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        actions = set(s.scalars(select(AuditLog.action).where(AuditLog.action.startswith("consent."))))
    assert actions == {"consent.recorded", "consent.withdrawn"}
    assert client.get("/audit", headers=parent).status_code == 403
