"""The three doors into today's work (docs/GO-LIVE-ENGAGEMENT.md F2): pure, and honest about minutes."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.modules.planner import sessions


def item(
    *, marks: int, reason: str = "retention_high", to_do: bool = True, objective: UUID | None = None
) -> sessions.Item:
    return sessions.Item(
        item_id=uuid4(),
        objective_id=objective or uuid4(),
        marks=marks,
        reason_code=reason,
        to_do=to_do,
    )


def test_minutes_are_about_a_minute_a_mark() -> None:
    assert sessions.minutes_for([item(marks=2), item(marks=3)]) == 5
    assert sessions.minutes_for([]) == 0


def test_the_short_door_takes_the_shortest_revision_questions_inside_its_budget() -> None:
    picked = sessions.quick_pick([item(marks=3), item(marks=1), item(marks=2)])
    assert sessions.minutes_for(picked) <= sessions.QUICK_MINUTES
    assert [i.marks for i in picked] == [1, 2]  # shortest first, and the 3-mark one would not fit


def test_the_short_door_only_offers_topics_due_for_revision_and_only_what_she_has_not_answered() -> None:
    due = item(marks=1, reason="retention_medium")
    assert sessions.quick_pick(
        [
            item(marks=1, reason="on_todays_plan"),
            item(marks=1, reason="open_mistake_high"),
            item(marks=1, reason="lesson_read"),
            item(marks=1, reason="retention_high", to_do=False),
            due,
        ]
    ) == [due]


def test_a_single_long_revision_question_is_still_offered_with_its_real_minutes() -> None:
    [only] = sessions.quick_pick([item(marks=8)])
    # The door would rather admit to eight minutes than hide the one thing that is due.
    assert sessions.minutes_for([only]) == 8 > sessions.QUICK_MINUTES


def test_the_short_door_closes_when_nothing_is_due() -> None:
    assert sessions.quick_pick([item(marks=2, reason="on_todays_plan")]) == []
    assert sessions.quick_pick([]) == []


def test_todays_door_counts_only_what_is_left() -> None:
    pool = [item(marks=2, to_do=False), item(marks=3), item(marks=1)]
    assert sessions.minutes_for(sessions.to_do(pool)) == 4
    assert len(sessions.to_do(pool)) == 2


def test_the_long_doors_candidates_are_todays_topics_in_the_rules_order_without_repeats() -> None:
    first, second = uuid4(), uuid4()
    pool = [
        item(marks=2, objective=first, to_do=False),  # answered: not a candidate on its own
        item(marks=2, objective=second),
        item(marks=2, objective=first),
        item(marks=2, objective=second),  # a second question on a topic already listed
    ]
    assert sessions.deep_candidates(pool) == [second, first]
    assert sessions.deep_candidates([item(marks=2, to_do=False)]) == []
    assert sessions.deep_candidates([]) == []
