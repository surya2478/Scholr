"""Master Router through the real API: session context and rules make no LLM call (AC-A1); vague messages ask."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.curriculum.models import Subject
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


def test_router_resolution_order(household_world: SimpleNamespace, auth_headers: Auth) -> None:
    w = household_world
    with w.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        maths_id = s.scalar(select(Subject.id).where(Subject.code == "igcse-maths"))
    gateway, transport, _ = scripted_gateway()
    client = TestClient(create_app(session_factory=w.factory, gateway=gateway))
    student = auth_headers("test|student")

    session = client.post(
        "/route", headers=student, json={"message": "explain this please", "subject_id": str(maths_id)}
    )
    assert session.json()["source"] == "session" and session.json()["subject_id"] == str(maths_id)

    rules = client.post("/route", headers=student, json={"message": "how does compound interest work"}).json()
    assert (rules["source"], rules["subject_id"]) == ("rules", str(maths_id))
    assert rules["objective_code"] in ("2.8", "2.9", None)  # two sections cover compound interest: may offer both
    reverse = client.post("/route", headers=student, json={"message": "reverse percentage"}).json()
    assert (reverse["source"], reverse["objective_code"]) == ("rules", "2.10")
    assert (
        client.post("/route", headers=student, json={"message": "what should I study today?"}).json()["intent"]
        == "plan"
    )
    assert transport.requests == []  # AC-A1: no router LLM call when context or rules are enough

    transport.reply({"intent": "explain", "subject_code": None, "objective_code": None, "confidence": 0.3})
    vague = client.post("/route", headers=student, json={"message": "can you help me with this thing"}).json()
    assert vague["source"] == "ask" and len(vague["choices"]) >= 1 and len(transport.requests) == 1

    assert client.post("/route", headers=auth_headers("test|parent"), json={"message": "hi"}).status_code == 403
