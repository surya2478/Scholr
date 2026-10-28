"""Unit tests for the Examination Builder and multi-topic question selector."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.assessment import service
from app.modules.assessment.schemas import ExamFromTopicsIn, QuestionsByObjectivesIn
from app.modules.assessment.service import TopicItem, fill_to_marks, order_for_topics


def test_exam_from_topics_schema_validation() -> None:
    subject_id = uuid4()
    obj1 = uuid4()
    obj2 = uuid4()

    exam = ExamFromTopicsIn(
        subject_id=subject_id,
        title="Mid-Term Mathematics Exam",
        exam_category="mid_term",
        objective_ids=[obj1, obj2],
        target_marks=50,
        duration_minutes=90,
    )
    assert exam.title == "Mid-Term Mathematics Exam"
    assert exam.exam_category == "mid_term"
    assert len(exam.objective_ids) == 2
    assert exam.duration_minutes == 90

    # Test invalid category
    with pytest.raises(ValidationError):
        ExamFromTopicsIn(
            subject_id=subject_id,
            title="Invalid",
            exam_category="unsupported_exam",  # type: ignore[arg-type]
            objective_ids=[obj1],
        )

    # Test empty objectives
    with pytest.raises(ValidationError):
        ExamFromTopicsIn(
            subject_id=subject_id,
            title="Empty",
            exam_category="term",
            objective_ids=[],
        )


def test_questions_by_objectives_schema_validation() -> None:
    obj = uuid4()
    query = QuestionsByObjectivesIn(subject_id=uuid4(), objective_ids=[obj], limit=15)
    assert query.limit == 15
    assert len(query.objective_ids) == 1

    # Empty objective list rejected
    with pytest.raises(ValidationError):
        QuestionsByObjectivesIn(subject_id=uuid4(), objective_ids=[], limit=10)


def test_topics_take_turns_and_new_questions_come_first() -> None:
    a, b = uuid4(), uuid4()
    a_big, a_small, a_done = TopicItem(uuid4(), 6, (a,)), TopicItem(uuid4(), 2, (a,)), TopicItem(uuid4(), 9, (a,))
    b_one = TopicItem(uuid4(), 3, (b, a))  # on both topics: offered once, under the first chosen (b)
    order = order_for_topics([a_big, a_small, a_done, b_one], [b, a], attempted={a_done.id})
    assert order == [b_one.id, a_big.id, a_small.id, a_done.id]


def test_an_exam_fills_towards_the_target_and_never_over_it() -> None:
    x, y, z = uuid4(), uuid4(), uuid4()
    marks = {x: 15, y: 8, z: 4}
    assert fill_to_marks([x, y, z], marks, 20) == [x, z]  # 15 + 4; the 8 would go over
    assert fill_to_marks([x, y, z], marks, 3) == []


def test_a_topic_exam_is_sat_under_exam_conditions_but_is_not_exam_evidence() -> None:
    assert service.TOPIC_EXAM in service.EXAM_CONDITION_KINDS
    assert service.TOPIC_EXAM not in service.EXAM_STYLE_KINDS  # mastery's exam weight and readiness sittings
