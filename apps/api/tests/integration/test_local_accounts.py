"""Register with an email, wait for the admin, then sign in (docs/STUDENT-APP.md D7, AC-U10).

Passwords below are fixtures for this test only.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.auth import issue_dev_token
from app.core.config import get_settings
from app.core.db import set_rls_context
from app.main import create_app
from app.modules.enrollment.models import Enrollment
from app.modules.identity.models import AppUser, Student

pytestmark = pytest.mark.db

PASSWORD = "correct-horse-battery"
NEW_ACCOUNT = {"email": "New.Student@example.com", "password": PASSWORD, "display_name": "New Student"}


@pytest.fixture
def local_client(household_world: SimpleNamespace) -> TestClient:
    settings = get_settings().model_copy(update={"auth_mode": "local"})
    with TestClient(create_app(settings=settings, session_factory=household_world.factory)) as client:
        yield client


def admin_headers(world: SimpleNamespace) -> dict[str, str]:
    """A seeded admin account. Roles come from the database, never from the token."""
    subject = f"test|admin-{uuid4()}"
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        tenant_id = s.scalar(select(AppUser.tenant_id).limit(1))
        s.add(
            AppUser(
                tenant_id=tenant_id,
                auth_subject=subject,
                email=f"{subject}@example.com",
                display_name="Admin",
                role="admin",
                status="active",
            )
        )
    return {"Authorization": f"Bearer {issue_dev_token(subject, get_settings())}"}


def register(client: TestClient, **overrides: Any) -> dict:
    body = {**NEW_ACCOUNT, "requested_streams": ["IGCSE"], **overrides}
    resp = client.post("/auth/register", json=body)
    assert resp.status_code == 202, resp.text
    return resp.json()


def test_a_new_account_waits_for_the_admin_then_signs_in_with_its_streams(
    household_world: SimpleNamespace, local_client: TestClient
) -> None:
    assert [s["key"] for s in local_client.get("/auth/streams").json()] == ["IGCSE", "IIT", "INDIA"]
    register(local_client)

    refused = local_client.post("/auth/sign-in", json={"email": NEW_ACCOUNT["email"], "password": PASSWORD})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "approval_pending"

    headers = admin_headers(household_world)
    [pending] = local_client.get("/admin/registrations", headers=headers).json()
    assert pending["email"] == "new.student@example.com"  # normalised
    assert pending["display_name"] == "New Student" and pending["requested_streams"] == ["IGCSE"]

    approved = local_client.post(
        f"/admin/registrations/{pending['user_id']}/approve",
        headers=headers,
        json={"role": "student", "streams": ["IGCSE"], "year_group": "Year 10"},
    )
    assert approved.status_code == 200, approved.text
    assert "igcse-maths" in approved.json()["subjects_enrolled"]
    assert local_client.get("/admin/registrations", headers=headers).json() == []

    signed_in = local_client.post("/auth/sign-in", json={"email": "new.student@example.com", "password": PASSWORD})
    assert signed_in.status_code == 200, signed_in.text
    me = local_client.get("/me", headers={"Authorization": f"Bearer {signed_in.json()['token']}"}).json()
    assert me["user"]["role"] == "student" and me["student"]["display_name"] == "New Student"
    assert [e["subject_code"] for e in me["student"]["enrollments"]] == ["igcse-maths"]

    with household_world.factory() as s:
        set_rls_context(s, user_id=None, role="system")
        student_id = s.scalar(select(Student.id).where(Student.display_name == "New Student"))
        assert s.scalars(select(Enrollment.subject_id).where(Enrollment.student_id == student_id)).all()


def test_a_rejected_account_can_never_sign_in(household_world: SimpleNamespace, local_client: TestClient) -> None:
    register(local_client)
    headers = admin_headers(household_world)
    [pending] = local_client.get("/admin/registrations", headers=headers).json()
    assert (
        local_client.post(
            f"/admin/registrations/{pending['user_id']}/reject", headers=headers, json={"reason": "not ours"}
        ).status_code
        == 204
    )
    refused = local_client.post("/auth/sign-in", json={"email": NEW_ACCOUNT["email"], "password": PASSWORD})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "account_not_active"
    # The decision is final: the same request cannot be approved afterwards.
    again = local_client.post(
        f"/admin/registrations/{pending['user_id']}/approve", headers=headers, json={"role": "student"}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_decided"


def test_registration_refuses_a_weak_password_and_hides_whether_an_address_is_known(local_client: TestClient) -> None:
    weak = local_client.post("/auth/register", json={**NEW_ACCOUNT, "password": "short"})
    assert weak.status_code == 409 and weak.json()["error"]["code"] == "weak_password"
    bad_email = local_client.post("/auth/register", json={**NEW_ACCOUNT, "email": "not-an-address"})
    assert bad_email.status_code == 409 and bad_email.json()["error"]["code"] == "invalid_email"

    register(local_client)
    # The same address again is answered exactly like the first time, and makes no second request.
    assert register(local_client, display_name="Impostor")["status"] == "pending"


def test_wrong_passwords_lock_the_account_and_say_nothing_about_the_address(
    household_world: SimpleNamespace, local_client: TestClient
) -> None:
    unknown = local_client.post("/auth/sign-in", json={"email": "nobody@example.com", "password": PASSWORD})
    assert unknown.status_code == 401
    register(local_client)
    headers = admin_headers(household_world)
    [pending] = local_client.get("/admin/registrations", headers=headers).json()
    local_client.post(f"/admin/registrations/{pending['user_id']}/approve", headers=headers, json={"role": "student"})
    attempts = get_settings().auth_login_attempts
    for _ in range(attempts):
        wrong = local_client.post("/auth/sign-in", json={"email": NEW_ACCOUNT["email"], "password": "wrong-password"})
        assert wrong.status_code == 401 and "wrong" in wrong.json()["error"]["message"]
    locked = local_client.post("/auth/sign-in", json={"email": NEW_ACCOUNT["email"], "password": PASSWORD})
    assert locked.status_code == 403 and locked.json()["error"]["code"] == "account_locked"


def test_only_an_admin_sees_or_decides_registrations(
    household_world: SimpleNamespace, local_client: TestClient
) -> None:
    register(local_client)
    student = {"Authorization": f"Bearer {issue_dev_token('test|student', get_settings())}"}
    assert local_client.get("/admin/registrations", headers=student).status_code == 403
    assert local_client.get("/admin/registrations").status_code == 401


def test_email_sign_in_does_not_exist_outside_local_mode(household_world: SimpleNamespace) -> None:
    with TestClient(create_app(session_factory=household_world.factory)) as dev_client:  # AUTH_MODE=dev
        assert dev_client.post("/auth/register", json=NEW_ACCOUNT).status_code == 404
        assert dev_client.post("/auth/sign-in", json={"email": "a@b.com", "password": PASSWORD}).status_code == 404
