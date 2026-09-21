from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.events.service import EventView
from app.modules.mastery.service import collect_evidence

T0 = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
OBJ_A, OBJ_B = uuid4(), uuid4()
STUDENT = uuid4()


def event(event_type: str, payload: dict[str, object], *, minutes: int, objectives: tuple[UUID, ...]) -> EventView:
    return EventView(
        id=uuid4(),
        student_id=STUDENT,
        type=event_type,
        occurred_at=T0 + timedelta(minutes=minutes),
        subject_id=None,
        objective_ids=objectives,
        payload=payload,
    )


def evaluated(evaluation_id: UUID, *, awarded: float, status: str = "final", minutes: int = 0, **kw: object):
    payload = {
        "attempt_id": str(uuid4()),
        "evaluation_id": str(evaluation_id),
        "marks_awarded": awarded,
        "marks_available": 4,
        "help_level": 0,
        "evaluation_confidence": 0.8,
        "status": status,
        **kw,
    }
    return event("attempt_evaluated", payload, minutes=minutes, objectives=(OBJ_A,))


def test_only_final_evaluations_count() -> None:
    e1, e2 = uuid4(), uuid4()
    evidence = collect_evidence([evaluated(e1, awarded=3), evaluated(e2, awarded=1, status="needs_review")])
    assert [e.evaluation_id for e in evidence] == [e1]
    assert evidence[0].item.score == 0.75
    assert evidence[0].item.evaluation_confidence == 0.8


def test_override_promotes_needs_review_with_full_confidence() -> None:
    e1 = uuid4()
    override = event(
        "evaluation_overridden",
        {
            "attempt_id": str(uuid4()),
            "evaluation_id": str(e1),
            "marks_awarded": 4,
            "marks_available": 4,
            "reviewer_user_id": str(uuid4()),
        },
        minutes=30,
        objectives=(OBJ_A,),
    )
    [evidence] = collect_evidence([evaluated(e1, awarded=1, status="needs_review", exam_style=True), override])
    assert evidence.overridden
    assert evidence.item.score == 1.0
    assert evidence.item.evaluation_confidence == 1.0
    assert evidence.item.exam_style  # flags come from the original evaluation


def test_multi_objective_attempt_counts_for_each_objective_and_later_duplicate_wins() -> None:
    e1 = uuid4()
    first = evaluated(e1, awarded=1)
    replay = EventView(**{**first.__dict__, "id": uuid4(), "objective_ids": (OBJ_A, OBJ_B)})
    replay.payload["marks_awarded"] = 2
    [evidence] = collect_evidence([first, replay])
    assert evidence.objective_ids == (OBJ_A, OBJ_B)
    assert evidence.item.score == 0.5


def test_override_without_evaluation_is_ignored() -> None:
    orphan = event(
        "evaluation_overridden",
        {
            "attempt_id": str(uuid4()),
            "evaluation_id": str(uuid4()),
            "marks_awarded": 1,
            "marks_available": 1,
            "reviewer_user_id": str(uuid4()),
        },
        minutes=0,
        objectives=(OBJ_A,),
    )
    assert collect_evidence([orphan]) == []
