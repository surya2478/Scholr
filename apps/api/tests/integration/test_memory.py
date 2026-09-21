"""Learning memory through the real database: summarizing an ended session (scripted summarizer), evidence rules,
job bookkeeping, and audited guardian reads."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import set_rls_context
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.curriculum.models import LearningObjective, Subject, Topic
from app.modules.events import service as events
from app.modules.memory import service as memory
from app.modules.memory.models import LearningMemory
from app.modules.tutoring import service as tutoring
from app.modules.tutoring.models import LearningSession
from tests.fixtures.llm import scripted_gateway

pytestmark = pytest.mark.db
Auth = Callable[..., dict[str, str]]


def test_session_summary_becomes_evidence_linked_memory(household_world: SimpleNamespace, auth_headers: Auth) -> None:
    w = household_world
    now = datetime.now(UTC)

    @contextmanager
    def system() -> Iterator[Session]:
        with w.factory() as s, s.begin():
            set_rls_context(s, user_id=None, role="system")
            yield s

    with system() as s:
        objective_id, subject_id = s.execute(
            select(LearningObjective.id, Subject.id)
            .join(Topic, Topic.id == LearningObjective.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Subject.code == "igcse-maths")
            .order_by(LearningObjective.code)
            .limit(1)
        ).one()
        busy = LearningSession(
            tenant_id=w.tenant_id,
            student_id=w.student_id,
            subject_id=subject_id,
            mode="practice",
            started_at=now - timedelta(minutes=30),
            ended_at=now - timedelta(minutes=1),
        )
        quiet = LearningSession(
            tenant_id=w.tenant_id,
            student_id=w.student_id,
            subject_id=subject_id,
            mode="learn",
            started_at=now - timedelta(hours=5),
            ended_at=now - timedelta(hours=4, minutes=50),
        )
        s.add_all([busy, quiet])
        s.flush()
        common = {
            "tenant_id": w.tenant_id,
            "student_id": w.student_id,
            "subject_id": subject_id,
            "objective_ids": [objective_id],
        }
        attempt, evaluation = uuid4(), uuid4()
        events.append(
            s,
            event_type="attempt_evaluated",
            occurred_at=now - timedelta(minutes=20),
            payload={
                "attempt_id": attempt,
                "evaluation_id": evaluation,
                "marks_awarded": 1,
                "marks_available": 3,
                "help_level": 3,
                "evaluation_confidence": 0.9,
                "status": "final",
            },
            **common,
        )
        events.append(
            s,
            event_type="mistake_diagnosed",
            occurred_at=now - timedelta(minutes=20),
            payload={
                "evaluation_id": evaluation,
                "attempt_id": attempt,
                "mistake_type": "calculation",
                "severity": "medium",
                "fingerprint": "calculation:premature_rounding",
            },
            **common,
        )
        busy_id, quiet_id = busy.id, quiet.id

    gateway, transport, _ = scripted_gateway()
    transport.reply(
        {
            "statements": [
                {
                    "kind": "misconception",
                    "statement": "Rounds too early in multi-step calculations on this objective.",
                    "evidence": ["E1", "E2"],
                },
                {"kind": "strength", "statement": "Enjoys geometry.", "evidence": []},
            ]
        }
    )

    quiet_report = memory.summarize_session(system, gateway, quiet_id, request_id="test-quiet", now=now)
    assert quiet_report.status == "little_activity" and transport.requests == []  # no LLM call for an idle session

    report = memory.summarize_session(system, gateway, busy_id, request_id="test-busy", now=now)
    assert (report.status, report.created, report.rejected) == ("summarized", 1, ("no_evidence",))
    prompt = transport.requests[-1].messages[-1]["content"]
    assert "calculation:premature_rounding" in prompt and str(attempt) not in prompt  # ids stay out of the prompt

    with system() as s:
        [row] = s.scalars(select(LearningMemory)).all()
        assert len(row.evidence_event_ids) == 2  # AC-M3
        assert tutoring.sessions_to_summarize(s) == []  # both sessions processed

    client = TestClient(create_app(session_factory=w.factory))
    [mine] = client.get("/memory", headers=auth_headers("test|student")).json()
    assert mine["kind"] == "misconception" and mine["evidence_count"] == 2
    assert client.get("/memory", headers=auth_headers("test|parent")).json() == [mine]
    with system() as s:
        assert s.scalar(select(AuditLog.id).where(AuditLog.action == "memory.read")) is not None  # AC-S2
