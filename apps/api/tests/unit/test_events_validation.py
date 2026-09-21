from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.events.models import EVENT_TYPES
from app.modules.events.schemas import PAYLOAD_SCHEMAS
from app.modules.events.service import EventValidationError, validate_event

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def evaluated(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "attempt_id": str(uuid4()),
        "evaluation_id": str(uuid4()),
        "marks_awarded": 2,
        "marks_available": 3,
        "help_level": 1,
        "evaluation_confidence": 0.9,
        "status": "final",
    }
    payload.update(overrides)
    return payload


def check(event_type: str, payload: dict[str, object], **kw: object) -> dict[str, object]:
    params: dict[str, object] = {"occurred_at": NOW, "objective_ids": [uuid4()], "now": NOW}
    params.update(kw)
    return validate_event(event_type, payload, **params)  # type: ignore[arg-type]


def test_every_event_type_has_a_payload_schema() -> None:
    assert set(PAYLOAD_SCHEMAS) == set(EVENT_TYPES)


def test_valid_payload_is_normalised() -> None:
    clean = check("attempt_evaluated", evaluated())
    assert clean["exam_style"] is False
    assert clean["marks_available"] == 3


def test_free_text_cannot_enter_the_event_log() -> None:
    with pytest.raises(EventValidationError) as exc:
        check("attempt_evaluated", evaluated(answer_text="x = 4"))
    assert "x = 4" not in str(exc.value)


def test_marks_awarded_cannot_exceed_available() -> None:
    with pytest.raises(EventValidationError):
        check("attempt_evaluated", evaluated(marks_awarded=4))


def test_objective_ids_required_for_projected_events() -> None:
    with pytest.raises(EventValidationError):
        check("attempt_evaluated", evaluated(), objective_ids=[])
    assert check("session_started", {"session_id": str(uuid4()), "mode": "learn"}, objective_ids=[]) is not None


@pytest.mark.parametrize(
    "occurred_at",
    [datetime(2026, 9, 14, 12, 0), NOW + timedelta(hours=1)],  # naive, future
)
def test_bad_timestamps_rejected(occurred_at: datetime) -> None:
    with pytest.raises(EventValidationError):
        check("attempt_evaluated", evaluated(), occurred_at=occurred_at)


def test_unknown_type_rejected() -> None:
    with pytest.raises(EventValidationError):
        check("grade_changed", {})
