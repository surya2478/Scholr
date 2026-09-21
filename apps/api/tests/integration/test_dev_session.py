"""Development sign-in: the app opens a seeded household account, and only ever in development mode."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.db


def test_dev_session_returns_a_working_token(household_world: SimpleNamespace, api_client: TestClient) -> None:
    resp = api_client.post("/dev/session", json={"role": "student"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_name"] == "Test Student"

    me = api_client.get("/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200 and me.json()["user"]["role"] == "student"

    guardian = api_client.post("/dev/session", json={"role": "guardian"}).json()
    linked = api_client.get("/me", headers={"Authorization": f"Bearer {guardian['token']}"}).json()
    assert linked["user"]["role"] == "guardian" and linked["linked_students"]


def test_dev_session_is_absent_unless_the_api_runs_in_dev_mode(household_world: SimpleNamespace) -> None:
    settings = get_settings().model_copy(update={"auth_mode": "jwks"})
    with TestClient(create_app(settings=settings, session_factory=household_world.factory)) as client:
        assert client.post("/dev/session", json={"role": "student"}).status_code == 404


def test_dev_session_rejects_an_unknown_role(household_world: SimpleNamespace, api_client: TestClient) -> None:
    assert api_client.post("/dev/session", json={"role": "admin"}).status_code == 422
