"""What did class cover today? Through the real API (docs/GO-LIVE-ENGAGEMENT.md F4, improvement 7).

The test household is enrolled in Mathematics (stage `taught`), whose real curriculum seed is loaded.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


@pytest.fixture
def client(household_world: SimpleNamespace) -> TestClient:
    return TestClient(create_app(session_factory=household_world.factory))


def test_two_taps_record_what_class_covered(client: TestClient, auth_headers: Auth) -> None:
    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    [maths] = client.get("/class-check-in", headers=student).json()["subjects"]
    assert maths["subject_name"] == "Mathematics" and maths["logged"] == []
    first = maths["suggestions"][0]
    assert len(maths["suggestions"]) == 4 and first["name"] == "Number"  # nothing logged yet: from chapter 1
    assert len(maths["suggestions"]) + len(maths["others"]) == 33  # every Collins chapter is offered

    body = {"subject_id": maths["subject_id"], "topic_id": first["topic_id"]}
    assert client.post("/class-check-in", headers=parent, json=body).status_code == 403  # her tap, not a parent's
    logged = client.post("/class-check-in", headers=student, json=body)
    assert logged.status_code == 201, logged.text
    [entry] = logged.json()["subjects"][0]["logged"]
    assert entry["name"] == "Number" and entry["next_objective_code"] == "1.1"  # where "lock it in tonight" opens
    again = client.post("/class-check-in", headers=student, json=body).json()["subjects"][0]["logged"]
    assert [x["entry_id"] for x in again] == [entry["entry_id"]]  # the same tap twice is recorded once

    # It is her teaching plan, current for a week, and the next plan treats it as the school topic.
    [row] = [e for e in client.get("/teaching-plan", headers=parent).json() if e["source"] == "class check-in"]
    assert row["topic_ids"] == [first["topic_id"]]
    assert row["starts_on"] and row["ends_on"] and row["starts_on"] < row["ends_on"]
    assert client.put(
        f"/students/{client.get('/me', headers=student).json()['student']['id']}/availability",
        headers=parent,
        json={"minutes": [120] * 7},
    ).json()
    plan = client.post("/plan/regenerate", headers=student).json()
    assert any(i["kind"] == "school_topic" and i["objective_code"].startswith("1.") for i in plan["items"])

    # Tomorrow's suggestions carry on from it; a wrong tap can be undone.
    assert client.delete(f"/teaching-plan/{entry['entry_id']}", headers=student).status_code == 204
    assert client.get("/class-check-in", headers=student).json()["subjects"][0]["logged"] == []


def test_only_a_chapter_of_that_subject_can_be_logged(client: TestClient, auth_headers: Auth) -> None:
    student = auth_headers("test|student")
    [maths] = client.get("/class-check-in", headers=student).json()["subjects"]
    unit = client.get(f"/subjects/{maths['subject_id']}/tree", headers=student).json()["topics"][0]["id"]
    refused = client.post(
        "/class-check-in", headers=student, json={"subject_id": maths["subject_id"], "topic_id": unit}
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "not_a_chapter")  # a unit is not a lesson
