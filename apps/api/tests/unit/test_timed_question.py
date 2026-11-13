"""This week's timed question: the week, the minutes and the choice are rules, not judgements (readiness/timed.py)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.modules.readiness import timed


def q(marks: int, *objectives, ref: str = "x"):  # noqa: ANN001, ANN201
    return SimpleNamespace(id=uuid4(), marks=marks, objective_ids=list(objectives), source_ref=ref)


def test_weeks_run_monday_to_sunday() -> None:
    assert timed.week_start(date(2026, 11, 13)) == date(2026, 11, 9)  # Friday -> Monday
    assert timed.week_start(date(2026, 11, 9)) == date(2026, 11, 9)
    assert timed.week_start(date(2026, 11, 15)) == date(2026, 11, 9)  # Sunday still belongs to it


def test_minutes_are_her_papers_pace() -> None:
    sociology = (120 + 105) * 60 / (80 + 80)  # both 0495 papers: 84.4 seconds a mark
    assert timed.minutes_for(14, sociology) == 20
    assert timed.minutes_for(10, sociology) == 15
    assert timed.minutes_for(1, 10) == 1


def test_the_choice_prefers_a_met_topic_then_the_bigger_question_and_never_repeats() -> None:
    met, unmet, held = uuid4(), uuid4(), uuid4()
    big_unmet, small_met, big_met = q(14, unmet, ref="a"), q(10, met, ref="b"), q(12, met, ref="c")
    pool = [big_unmet, small_met, big_met]
    assert timed.choose(pool, met={met}, answered=set(), held_back=set()) is big_met
    assert timed.choose(pool, met={met}, answered={big_met.id}, held_back=set()) is small_met
    assert timed.choose(pool, met=set(), answered=set(), held_back=set()) is big_unmet
    # Never on a topic the validation study holds back, and nothing at all when the bank is spent.
    assert timed.choose([q(14, held)], met=set(), answered=set(), held_back={held}) is None
    assert timed.choose([big_met], met={met}, answered={big_met.id}, held_back=set()) is None
    assert timed.choose([q(14)], met=set(), answered=set(), held_back=set()) is None  # untagged: no topic to name


def test_only_subjects_marked_in_levels_get_one() -> None:
    assert timed.eligible("igcse-sociology") is True
    assert timed.eligible("igcse-maths") is False  # structured marking, short parts
    assert timed.eligible("igcse-physics") is False  # lessons only, nothing marked yet
    assert timed.eligible("no-such-subject") is False


def test_a_newer_paper_comes_before_a_bigger_old_one() -> None:
    topic = uuid4()
    old_big = q(15, topic, ref="0495/11/MJ23/Q1(g)")  # the 2023 format's 15-mark question
    new = q(14, topic, ref="0495/21/MJ25/Q2(f)")  # shaped like the papers she will sit
    assert timed.choose([old_big, new], met={topic}, answered=set(), held_back=set()) is new
