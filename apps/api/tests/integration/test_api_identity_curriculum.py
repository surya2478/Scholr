"""GET /me, /subjects, /subjects/{id}/tree, /objectives/{id} through the real app, database and RLS."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.seed.curriculum import TopicIn

pytestmark = pytest.mark.db

Auth = Callable[..., dict[str, str]]


def _count_objectives(topics: list[TopicIn]) -> int:
    return sum(len(t.objectives) + _count_objectives(t.children) for t in topics)


def test_health_needs_no_auth(api_client: TestClient) -> None:
    assert api_client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer not-a-jwt"}, {"Authorization": "Basic abc"}],
)
def test_missing_or_bad_token_is_401(api_client: TestClient, headers: dict[str, str]) -> None:
    resp = api_client.get("/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_a_valid_token_in_the_url_is_refused(api_client: TestClient, auth_headers: Auth) -> None:
    """Tokens travel only in the Authorization header: one in the query string would land in access logs, proxy
    logs and browser history (review of 21 Sep 2026)."""
    token = auth_headers("test|student")["Authorization"].removeprefix("Bearer ")
    assert api_client.get("/me", headers=auth_headers("test|student")).status_code == 200
    assert api_client.get("/me", params={"token": token}).status_code == 401


def test_valid_token_for_unknown_user_is_401(api_client: TestClient, auth_headers: Auth) -> None:
    assert api_client.get("/me", headers=auth_headers("test|nobody")).status_code == 401


def test_student_me_shows_profile_enrollments_and_guardian_visibility(
    api_client: TestClient, auth_headers: Auth
) -> None:
    resp = api_client.get("/me", headers={**auth_headers("test|student"), "X-Request-ID": "req-test-0001"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "req-test-0001"
    body = resp.json()
    assert body["user"]["role"] == "student"
    assert body["student"]["display_name"] == "Test Student"
    assert [(e["subject_code"], e["tier"]) for e in body["student"]["enrollments"]] == [("igcse-maths", "extended")]
    assert [g["guardian_name"] for g in body["guardian_visibility"]] == ["Other Parent", "Test Parent"]
    assert "conversations" in body["guardian_visibility"][0]["scopes"]
    assert body["linked_students"] == []


def test_guardian_me_lists_linked_student_through_rls(api_client: TestClient, auth_headers: Auth) -> None:
    body = api_client.get("/me", headers=auth_headers("test|parent")).json()
    assert body["user"]["role"] == "guardian"
    assert body["student"] is None
    [linked] = body["linked_students"]
    assert linked["display_name"] == "Test Student"
    assert linked["enrollments"][0]["exam_session"] == "2028-06"


def test_guardian_without_mfa_is_refused(api_client: TestClient, auth_headers: Auth) -> None:
    resp = api_client.get("/me", headers=auth_headers("test|parent", mfa=False))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "mfa_required"


def test_subjects_tree_and_objective(
    api_client: TestClient, household_world: SimpleNamespace, auth_headers: Auth
) -> None:
    headers = auth_headers("test|student")
    maths_file = household_world.maths
    subjects = api_client.get("/subjects", headers=headers).json()
    [maths] = [s for s in subjects if s["code"] == "igcse-maths"]
    assert maths["syllabus_code"] == maths_file.syllabus.code
    assert len(maths["components"]) == len(maths_file.components)

    tree = api_client.get(f"/subjects/{maths['id']}/tree", headers=headers).json()
    assert len(tree["topics"]) == len(maths_file.topics)

    def walk(nodes: list[dict]) -> list[dict]:
        return [o for n in nodes for o in n["objectives"] + walk(n["children"])]

    objectives = walk(tree["topics"])
    assert len(objectives) == _count_objectives(maths_file.topics)

    detail = api_client.get(f"/objectives/{objectives[0]['id']}", headers=headers).json()
    assert detail["subject_code"] == "igcse-maths"
    assert detail["topic_path"][0]["code"] == tree["topics"][0]["code"]


def test_unknown_ids_and_malformed_ids(api_client: TestClient, auth_headers: Auth) -> None:
    headers = auth_headers("test|student")
    missing = api_client.get(f"/objectives/{uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert api_client.get(f"/subjects/{uuid4()}/tree", headers=headers).status_code == 404
    malformed = api_client.get("/objectives/not-a-uuid", headers=headers)
    assert malformed.status_code == 422
    assert malformed.json()["error"]["fields"] == ["path.objective_id"]


def test_household_seed_runs_twice(household_world: SimpleNamespace) -> None:
    """Re-seeding must be safe: the seed is the way the family's own details are corrected."""
    from sqlalchemy import select

    from app.core.db import set_rls_context
    from app.modules.enrollment.models import Commitment
    from app.seed.household import HouseholdIn, seed_household

    from .conftest import TEST_HOUSEHOLD

    household = {
        **TEST_HOUSEHOLD,
        "commitments": [
            {
                "kind": "iit_class",
                "title": "IIT Foundation — Mathematics",
                "rrule": "FREQ=WEEKLY;BYDAY=SA",
                "start_time": "15:30",
                "duration_min": 120,
                "notes": "Online",
            }
        ],
    }
    with household_world.factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        seed_household(s, HouseholdIn.model_validate(household))
        seed_household(s, HouseholdIn.model_validate(household))  # the second run used to raise
        rows = list(s.scalars(select(Commitment).where(Commitment.student_id == household_world.student_id)))
    assert len(rows) == 1
    assert rows[0].notes == "Online"
