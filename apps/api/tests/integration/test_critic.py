"""The Study Critic through the real API: it reads events, and both people read the same list (AC-C1..C3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.events import service as events

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


@pytest.fixture
def world(household_world: SimpleNamespace) -> SimpleNamespace:
    client = TestClient(create_app(session_factory=household_world.factory))
    return SimpleNamespace(**vars(household_world), client=client)


def plant(world: SimpleNamespace, *, days_ago: int, event_type: str, payload: dict, subject_id=None) -> None:
    when = datetime.now(UTC) - timedelta(days=days_ago)
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        events.append(
            s,
            tenant_id=world.tenant_id,
            student_id=world.student_id,
            event_type=event_type,
            occurred_at=when,
            payload=payload,
            subject_id=subject_id,
        )


def session_on(world: SimpleNamespace, days_ago: int, minutes: int) -> None:
    plant(
        world,
        days_ago=days_ago,
        event_type="session_ended",
        payload={"session_id": uuid4(), "active_minutes": minutes},
    )


def days_ago_in_week(weeks_back: int, weekday: int) -> int:
    """Days ago for a given weekday of a completed calendar week.

    The rule groups by calendar week (Monday start), so planting at a rolling seven-day offset lands the
    same pair in different weeks depending on which day the test runs — and makes any count assertion flaky.
    """
    today = datetime.now(UTC).date()
    monday_this_week = today - timedelta(days=today.weekday())
    target = monday_this_week - timedelta(weeks=weeks_back) + timedelta(days=weekday)
    return (today - target).days


def cram_three_weeks(world: SimpleNamespace) -> None:
    """Three completed weeks in which Monday carries almost everything."""
    for weeks_back in (1, 2, 3):
        session_on(world, days_ago=days_ago_in_week(weeks_back, 0), minutes=180)
        session_on(world, days_ago=days_ago_in_week(weeks_back, 2), minutes=15)


def test_a_quiet_month_says_so_rather_than_inventing_concern(world: SimpleNamespace, auth_headers: Auth) -> None:
    body = world.client.get("/study-patterns", headers=auth_headers("test|student")).json()
    assert body["patterns"] == []
    assert body["nothing_stands_out"]
    assert body["rule_version"] and body["template_version"]


def test_cramming_is_found_from_events_alone(world: SimpleNamespace, auth_headers: Auth) -> None:  # AC-C1
    cram_three_weeks(world)

    body = world.client.get("/study-patterns", headers=auth_headers("test|student")).json()
    kinds = {p["kind"] for p in body["patterns"]}
    assert "cramming" in kinds
    pattern = next(p for p in body["patterns"] if p["kind"] == "cramming")
    assert pattern["facts"]["weeks"] == "3"
    assert "%" in pattern["observation"], "the observation must carry its own numbers"
    assert body["study_minutes"] > 0


def test_the_student_and_the_guardian_see_the_same_patterns(world: SimpleNamespace, auth_headers: Auth) -> None:
    """AC-C3: different wording, never a different list — nothing is said behind her back."""
    cram_three_weeks(world)

    student = world.client.get("/study-patterns", headers=auth_headers("test|student")).json()
    guardian = world.client.get(
        f"/study-patterns?student_id={world.student_id}", headers=auth_headers("test|parent")
    ).json()

    assert [p["kind"] for p in student["patterns"]] == [p["kind"] for p in guardian["patterns"]]
    assert [p["severity"] for p in student["patterns"]] == [p["severity"] for p in guardian["patterns"]]
    assert student["patterns"][0]["observation"] != guardian["patterns"][0]["observation"], "voices differ"


def test_the_student_can_read_the_wording_her_parent_gets(world: SimpleNamespace, auth_headers: Auth) -> None:
    cram_three_weeks(world)

    student = auth_headers("test|student")
    hers = world.client.get("/study-patterns?audience=student", headers=student).json()
    theirs = world.client.get("/study-patterns?audience=guardian", headers=student).json()
    parent = world.client.get(
        f"/study-patterns?student_id={world.student_id}", headers=auth_headers("test|parent")
    ).json()

    assert theirs["patterns"][0]["observation"] == parent["patterns"][0]["observation"]
    assert hers["patterns"][0]["observation"] != theirs["patterns"][0]["observation"]


def test_old_events_fall_out_of_the_window(world: SimpleNamespace, auth_headers: Auth) -> None:
    for weeks_back in (9, 10, 11):
        session_on(world, days_ago=days_ago_in_week(weeks_back, 0), minutes=180)
        session_on(world, days_ago=days_ago_in_week(weeks_back, 2), minutes=15)
    body = world.client.get("/study-patterns", headers=auth_headers("test|student")).json()
    assert body["patterns"] == [], "a pattern from two months ago is not this month's pattern"
    assert body["study_minutes"] == 0


def test_a_guardian_without_a_link_is_refused(world: SimpleNamespace, auth_headers: Auth) -> None:
    refused = world.client.get(f"/study-patterns?student_id={uuid4()}", headers=auth_headers("test|parent"))
    assert refused.status_code in (400, 403)
