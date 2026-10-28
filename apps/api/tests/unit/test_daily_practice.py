"""The daily practice set rule (docs/STUDENT-APP.md step 4): pure, deterministic, and it never sets what it must not."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.modules.planner import daily


def objectives(n: int) -> list[UUID]:
    return [uuid4() for _ in range(n)]


def test_one_question_per_wanted_objective_first_in_order_of_claim() -> None:
    a, b, c = objectives(3)
    items = {o: [daily.Candidate(uuid4(), 2), daily.Candidate(uuid4(), 3)] for o in (a, b, c)}
    wants = [daily.Want(a, "on_todays_plan"), daily.Want(b, "open_mistake_high"), daily.Want(c, "retention_high")]
    picks = daily.choose(wants, items, recent=set(), excluded=set(), seed="s", size=3)
    assert [(p.objective_id, p.reason_code) for p in picks] == [
        (a, "on_todays_plan"),
        (b, "open_mistake_high"),
        (c, "retention_high"),
    ]


def test_a_short_set_takes_a_second_question_from_the_earliest_objectives() -> None:
    a, b = objectives(2)
    items = {o: [daily.Candidate(uuid4(), 2) for _ in range(3)] for o in (a, b)}
    picks = daily.choose([daily.Want(a, "x"), daily.Want(b, "y")], items, recent=set(), excluded=set(), seed="s")
    assert [p.objective_id for p in picks] == [a, b, a, b]
    assert len({p.item_id for p in picks}) == 4  # never the same question twice


def test_the_first_reason_an_objective_is_wanted_for_is_the_one_shown() -> None:
    (a,) = objectives(1)
    items = {a: [daily.Candidate(uuid4(), 1)]}
    wants = [daily.Want(a, "on_todays_plan"), daily.Want(a, "lesson_read")]
    [pick] = daily.choose(wants, items, recent=set(), excluded=set(), seed="s")
    assert pick.reason_code == "on_todays_plan"


def test_recent_questions_and_excluded_topics_are_never_set() -> None:
    a, b = objectives(2)
    done, fresh = daily.Candidate(uuid4(), 2), daily.Candidate(uuid4(), 2)
    items = {a: [done, fresh], b: [daily.Candidate(uuid4(), 2)]}
    picks = daily.choose([daily.Want(a, "x"), daily.Want(b, "y")], items, recent={done.item_id}, excluded={b}, seed="s")
    assert [p.item_id for p in picks] == [fresh.item_id]


def test_short_questions_first_and_the_same_day_gives_the_same_set() -> None:
    (a,) = objectives(1)
    long_one = daily.Candidate(uuid4(), 8)
    short = [daily.Candidate(uuid4(), 2) for _ in range(5)]
    items = {a: [long_one, *short]}
    first = daily.choose([daily.Want(a, "x")], items, recent=set(), excluded=set(), seed="student:2026-09-19")
    again = daily.choose([daily.Want(a, "x")], items, recent=set(), excluded=set(), seed="student:2026-09-19")
    assert first == again and first[0].item_id != long_one.item_id
    other_days = {
        daily.choose([daily.Want(a, "x")], items, recent=set(), excluded=set(), seed=f"student:2026-09-{d}")[0].item_id
        for d in range(10, 30)
    }
    assert len(other_days) > 1  # it varies across days


def test_nothing_to_set_is_an_empty_set_not_an_error() -> None:
    (a,) = objectives(1)
    assert daily.choose([daily.Want(a, "x")], {}, recent=set(), excluded=set(), seed="s") == []


def test_a_preview_names_at_most_three_topics_in_order_of_claim() -> None:
    a, b, c, d = objectives(4)
    items = {o: [daily.Candidate(uuid4(), 2), daily.Candidate(uuid4(), 2)] for o in (a, b, c, d)}
    wants = [
        daily.Want(a, "open_mistake_high"),
        daily.Want(b, "retention_high"),
        daily.Want(c, "retention_medium"),
        daily.Want(d, "lesson_read"),
    ]
    picks = daily.choose(wants, items, recent=set(), excluded=set(), seed="s", size=daily.PREVIEW_SIZE)
    assert [p.objective_id for p in picks] == [a, b, c]


def test_a_preview_names_nothing_when_every_question_is_recent() -> None:
    (a,) = objectives(1)
    answered = [daily.Candidate(uuid4(), 2), daily.Candidate(uuid4(), 2)]
    picks = daily.choose(
        [daily.Want(a, "lesson_read")],
        {a: answered},
        recent={c.item_id for c in answered},
        excluded=set(),
        seed="s",
        size=daily.PREVIEW_SIZE,
    )
    assert picks == []
