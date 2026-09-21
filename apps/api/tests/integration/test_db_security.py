"""AC-S1 (row-level security) and AC-A4 (append-only learning events)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.db import Role, set_rls_context
from app.modules.audit.models import AuditLog
from app.modules.events.models import LearningEvent
from app.modules.identity.models import GUARDIAN_SCOPES, AppUser, Guardian, GuardianStudentLink, Student, Tenant
from app.modules.planner.models import Goal

pytestmark = pytest.mark.db


@contextmanager
def acting(engine: Engine, role: Role | None, user_id: UUID | None = None) -> Iterator[Session]:
    with Session(engine) as session, session.begin():
        if role is not None:
            set_rls_context(session, user_id=user_id, role=role)
        yield session


def goal(tenant_id: UUID, student_id: UUID, statement: str) -> Goal:
    """A minimal valid goal. The security tests care only that it is a student-scoped row."""
    return Goal(
        tenant_id=tenant_id,
        student_id=student_id,
        kind="topics_secure",
        statement=statement,
        measure="topics_secure",
        target_value=1,
        proposed_by_role="student",
        rule_version="goals_v1",
    )


@pytest.fixture
def world(engine: Engine, clean_db: None) -> SimpleNamespace:
    with acting(engine, "system") as s:
        tenant = Tenant(name="Test family")
        s.add(tenant)
        s.flush()
        users = {
            key: AppUser(tenant_id=tenant.id, auth_subject=f"test|{key}", display_name=key, role=role)
            for key, role in [("a", "student"), ("b", "student"), ("g", "guardian"), ("admin", "admin")]
        }
        s.add_all(users.values())
        s.flush()
        student_a = Student(tenant_id=tenant.id, user_id=users["a"].id, display_name="A", year_group="Year 10")
        student_b = Student(tenant_id=tenant.id, user_id=users["b"].id, display_name="B", year_group="Year 10")
        guardian = Guardian(tenant_id=tenant.id, user_id=users["g"].id)
        s.add_all([student_a, student_b, guardian])
        s.flush()
        link = GuardianStudentLink(
            tenant_id=tenant.id, guardian_id=guardian.id, student_id=student_a.id, scopes=list(GUARDIAN_SCOPES)
        )
        s.add(link)
        s.add_all([goal(tenant.id, student_a.id, "A goal"), goal(tenant.id, student_b.id, "B goal")])
        s.flush()
        return SimpleNamespace(
            tenant=tenant.id,
            user_a=users["a"].id,
            user_b=users["b"].id,
            user_g=users["g"].id,
            user_admin=users["admin"].id,
            student_a=student_a.id,
            student_b=student_b.id,
            link=link.id,
        )


def visible_goals(engine: Engine, role: Role | None, user_id: UUID | None) -> list[str]:
    with acting(engine, role, user_id) as s:
        return sorted(s.scalars(select(Goal.statement)))


def test_student_sees_only_own_rows(engine: Engine, world: SimpleNamespace) -> None:
    assert visible_goals(engine, "student", world.user_a) == ["A goal"]
    assert visible_goals(engine, "student", world.user_b) == ["B goal"]


def test_guardian_sees_only_linked_student(engine: Engine, world: SimpleNamespace) -> None:
    assert visible_goals(engine, "guardian", world.user_g) == ["A goal"]


def test_no_context_sees_nothing(engine: Engine, world: SimpleNamespace) -> None:
    assert visible_goals(engine, None, None) == []


def test_role_claim_without_matching_user_sees_nothing(engine: Engine, world: SimpleNamespace) -> None:
    assert visible_goals(engine, "student", world.user_g) == []


def test_admin_and_system_see_all(engine: Engine, world: SimpleNamespace) -> None:
    assert visible_goals(engine, "admin", world.user_admin) == ["A goal", "B goal"]


def test_student_cannot_write_for_another_student(engine: Engine, world: SimpleNamespace) -> None:
    with pytest.raises(DBAPIError), acting(engine, "student", world.user_a) as s:
        s.add(goal(world.tenant, world.student_b, "sneaky"))
        s.flush()


def test_revoked_guardian_loses_access(engine: Engine, world: SimpleNamespace) -> None:
    with acting(engine, "system") as s:
        s.get(GuardianStudentLink, world.link).revoked_at = datetime.now(UTC)  # type: ignore[union-attr]
    assert visible_goals(engine, "guardian", world.user_g) == []


def test_learning_event_is_append_only(engine: Engine, world: SimpleNamespace) -> None:
    with acting(engine, "system") as s:
        event = LearningEvent(
            tenant_id=world.tenant, student_id=world.student_a, occurred_at=datetime.now(UTC), type="session_started"
        )
        s.add(event)
        s.flush()
        event_id = event.id
    for statement in (
        "UPDATE learning_event SET type = 'tampered' WHERE id = :id",
        "DELETE FROM learning_event WHERE id = :id",
    ):
        # Blocked twice over: the app role lacks UPDATE/DELETE, and a trigger rejects them for any role.
        with pytest.raises(DBAPIError, match="append-only|permission denied"), acting(engine, "system") as s:
            s.execute(text(statement), {"id": event_id})


def test_audit_log_writable_by_actor_but_readable_only_by_admin(engine: Engine, world: SimpleNamespace) -> None:
    with acting(engine, "student", world.user_a) as s:
        s.add(
            AuditLog(
                tenant_id=world.tenant,
                actor_user_id=world.user_a,
                actor_role="student",
                action="test.action",
                entity_type="goal",
                student_id=world.student_a,
            )
        )
    with acting(engine, "student", world.user_a) as s:
        assert s.scalars(select(AuditLog)).all() == []
    with acting(engine, "admin", world.user_admin) as s:
        assert len(s.scalars(select(AuditLog)).all()) == 1
