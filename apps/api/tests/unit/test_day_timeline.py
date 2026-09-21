"""My Day timeline: commitments keep their times, plan items fill the gaps around them (planner v1)."""

from __future__ import annotations

from datetime import time

from app.modules.planner.engine import FixedBlock, schedule_day

SCHOOL = FixedBlock("School", "Classes & homework", time(8, 0), 420)
IIT = FixedBlock("IIT Foundation — Physics/Chemistry", "IIT class", time(16, 30), 120)


def test_items_are_placed_around_commitments_in_plan_order() -> None:
    items = [("assessment", "Mathematics", "Quadratic equations", 30), ("practice", "Sociology", "Norms", 20)]
    blocks = schedule_day(items, [SCHOOL, IIT], weekend=False)
    assert [(b.title, b.start, b.end) for b in blocks] == [
        ("School", time(8, 0), time(15, 0)),
        ("IIT Foundation — Physics/Chemistry", time(16, 30), time(18, 30)),
        ("Mathematics", time(18, 35), time(19, 5)),
        ("Sociology", time(19, 10), time(19, 30)),
    ]


def test_a_gap_before_a_commitment_is_used_when_it_is_long_enough() -> None:
    blocks = schedule_day([("revision", "Mathematics", None, 20)], [IIT], weekend=False)
    maths = next(b for b in blocks if b.title == "Mathematics")
    assert (maths.start, maths.end) == (time(16, 0), time(16, 20))  # the 16:00–16:30 gap before the class


def test_items_that_do_not_fit_keep_their_place_without_a_time() -> None:
    long_class = FixedBlock("IIT Foundation", None, time(16, 0), 300)  # fills the weekday window
    blocks = schedule_day([("practice", "Sociology", None, 20)], [long_class], weekend=False)
    unplaced = [b for b in blocks if b.start is None]
    assert [(b.title, b.item_index, b.minutes) for b in unplaced] == [("Sociology", 0, 20)]


def test_the_weekend_window_starts_in_the_morning() -> None:
    [block] = schedule_day([("practice", "Mathematics", None, 45)], [], weekend=True)
    assert (block.start, block.end) == (time(9, 0), time(9, 45))
