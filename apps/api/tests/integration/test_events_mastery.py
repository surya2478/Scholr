"""AC-A3: mastery is a projection of append-only events, rebuildable, and served only to permitted users."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import Role, set_rls_context
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events import service as events
from app.modules.mastery import service as mastery
from app.modules.mastery.models import MasteryState
from app.modules.mastery.rules import MasteryLevel

pytestmark = pytest.mark.db

NOW = datetime.now(UTC).replace(microsecond=0)


@contextmanager
def acting(world: SimpleNamespace, role: Role, user_id: UUID | None = None) -> Iterator[Session]:
    with world.factory() as s, s.begin():
        set_rls_context(s, user_id=user_id, role=role)
        yield s


def first_objective(world: SimpleNamespace) -> tuple[UUID, UUID]:
    with acting(world, "system") as s:
        row = s.execute(
            select(LearningObjective.id, Subject.id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(1)
        ).one()
    return row[0], row[1]


def evaluated_event(
    s: Session, world: SimpleNamespace, objective_id: UUID, *, days_ago: int, awarded: float, **flags: object
) -> events.EventView:
    return events.append(
        s,
        tenant_id=world.tenant_id,
        student_id=world.student_id,
        event_type="attempt_evaluated",
        occurred_at=NOW - timedelta(days=days_ago),
        objective_ids=[objective_id],
        payload={
            "attempt_id": uuid4(),
            "evaluation_id": uuid4(),
            "marks_awarded": awarded,
            "marks_available": 3,
            "help_level": 0,
            "evaluation_confidence": 0.9,
            "status": flags.pop("status", "final"),
            **flags,
        },
    )


def mastery_rows(world: SimpleNamespace) -> list[tuple]:
    with acting(world, "system") as s:
        return [
            (r.objective_id, r.level, r.score, r.mastery_confidence, r.evidence_count, r.retention_risk)
            for r in s.scalars(select(MasteryState).where(MasteryState.student_id == world.student_id))
        ]


def test_events_project_to_mastery_and_rebuild_matches(household_world: SimpleNamespace) -> None:
    world = household_world
    objective_id, _ = first_objective(world)

    with acting(world, "student", world.student_user_id) as s:  # written under the student's own RLS context
        new = [
            evaluated_event(s, world, objective_id, days_ago=2, awarded=3),
            evaluated_event(s, world, objective_id, days_ago=1, awarded=3),
            evaluated_event(s, world, objective_id, days_ago=0, awarded=3, exam_style=True),
        ]
        pending = evaluated_event(s, world, objective_id, days_ago=0, awarded=0, status="needs_review")
        mastery.project(s, [*new, pending], tenant_id=world.tenant_id, now=NOW)

    [(_, level, score, _, evidence_count, _)] = mastery_rows(world)
    assert level == MasteryLevel.MASTERED
    assert score == 1.0
    assert evidence_count == 3  # needs_review does not count

    with acting(world, "system") as s:
        override = events.append(
            s,
            tenant_id=world.tenant_id,
            student_id=world.student_id,
            event_type="evaluation_overridden",
            occurred_at=NOW,
            objective_ids=[objective_id],
            payload={
                "attempt_id": pending.payload["attempt_id"],
                "evaluation_id": pending.payload["evaluation_id"],
                "marks_awarded": 2,
                "marks_available": 3,
                "reviewer_user_id": uuid4(),
            },
        )
        mastery.project(s, [override], tenant_id=world.tenant_id, now=NOW)
    [(_, _, score_after, _, evidence_after, _)] = mastery_rows(world)
    assert evidence_after == 4
    assert score_after < 1.0

    before = mastery_rows(world)
    with acting(world, "system") as s:
        assert mastery.rebuild(s, tenant_id=world.tenant_id, student_id=world.student_id, now=NOW) == 1
    assert mastery_rows(world) == before


def test_mastery_api_is_scoped_to_permitted_students(
    api_client: TestClient, household_world: SimpleNamespace, auth_headers: Callable[..., dict[str, str]]
) -> None:
    world = household_world
    objective_id, subject_id = first_objective(world)
    with acting(world, "system") as s:
        new = [evaluated_event(s, world, objective_id, days_ago=d, awarded=2) for d in (3, 2, 1)]
        mastery.project(s, new, tenant_id=world.tenant_id, now=NOW)

    student, parent = auth_headers("test|student"), auth_headers("test|parent")
    [row] = api_client.get("/mastery", headers=student).json()
    assert row["objective_id"] == str(objective_id)
    assert row["level_name"] == "Developing"
    assert api_client.get("/mastery", headers=parent).json() == [row]
    assert api_client.get(f"/mastery?subject_id={subject_id}", headers=student).json() == [row]
    assert api_client.get(f"/mastery?subject_id={uuid4()}", headers=student).json() == []

    evidence = api_client.get(f"/mastery/{objective_id}/evidence", headers=parent).json()
    assert len(evidence) == 3 and not any(e["overridden"] for e in evidence)

    for headers in (student, parent):
        denied = api_client.get(f"/mastery?student_id={uuid4()}", headers=headers)
        assert denied.status_code == 403
