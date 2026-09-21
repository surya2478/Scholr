"""Learning engine: AC-L1 (ask for an attempt first), AC-L2 (escalation), AC-L3 (isomorphic follow-up), guards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.tutoring.engine import (
    GENERAL_LABEL,
    LIMITED_NOTE,
    SERVED_MEMORY,
    GroundingPlan,
    ItemCandidate,
    ItemProgress,
    SessionState,
    after_help,
    choose_item,
    decide_help,
    grounding_plan,
    leaks_answer,
    start_item,
)
from app.modules.tutoring.policy import HelpLevel

NOW = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
OBJ = uuid4()


def test_state_round_trips_through_json() -> None:
    state = SessionState(phase="await_attempt", item_id="x", help_level=2, help_requests=("2026-10-05T16:00:00+00:00",))
    assert SessionState.load(state.dump()) == state
    assert SessionState.load(None) == SessionState()


def test_first_help_request_without_attempt_asks_for_an_attempt_then_helps() -> None:  # AC-L1
    state = start_item(SessionState(), uuid4(), [OBJ])
    first = decide_help(state, progress=ItemProgress(0, 0), mastery_level=1, now=NOW)
    assert first.action == "ask_for_attempt"
    state = after_help(state, first, NOW)
    second = decide_help(state, progress=ItemProgress(0, 0), mastery_level=1, now=NOW + timedelta(minutes=10))
    assert (second.action, second.level) == ("give_help", HelpLevel.NUDGE)


def test_misses_set_a_floor_from_the_escalation_table() -> None:  # AC-L2
    state = start_item(SessionState(), uuid4(), [OBJ])
    developing = decide_help(state, progress=ItemProgress(1, 1), mastery_level=1, now=NOW)
    assert developing.level == HelpLevel.HINT
    mastered = decide_help(state, progress=ItemProgress(1, 1), mastery_level=4, now=NOW)
    assert mastered.level == HelpLevel.NUDGE
    fourth_miss = decide_help(state, progress=ItemProgress(4, 4), mastery_level=2, now=NOW)
    assert fourth_miss.level == HelpLevel.FULL_SOLUTION


def test_repeated_requests_escalate_and_frustration_escalates_faster() -> None:
    state = start_item(SessionState(), uuid4(), [OBJ])
    state = after_help(state, decide_help(state, progress=ItemProgress(1, 0), mastery_level=3, now=NOW), NOW)
    assert state.help_level == HelpLevel.NUDGE
    rushed = NOW + timedelta(minutes=1)
    state = after_help(state, decide_help(state, progress=ItemProgress(1, 0), mastery_level=3, now=rushed), rushed)
    third = decide_help(state, progress=ItemProgress(1, 0), mastery_level=3, now=NOW + timedelta(minutes=2))
    assert third.level == HelpLevel.NEXT_STEP  # third request within 5 minutes: two levels up


def test_full_solution_requires_an_isomorphic_follow_up() -> None:  # AC-L3
    state = start_item(SessionState(), uuid4(), [OBJ])
    decision = decide_help(state, progress=ItemProgress(4, 4), mastery_level=1, now=NOW)
    state = after_help(state, decision, NOW, [OBJ])
    assert state.needs_isomorphic and state.isomorphic_objective_ids == (str(OBJ),)
    other = start_item(state, uuid4(), [uuid4()])
    assert other.needs_isomorphic
    same = start_item(state, uuid4(), [OBJ])
    assert not same.needs_isomorphic and same.help_level == 0


def candidate(objectives: tuple, marks: int = 2, ref: str = "q") -> ItemCandidate:  # noqa: ANN001
    return ItemCandidate(uuid4(), objectives, marks, ref)


def test_choose_item_priorities() -> None:
    weak, strong, mistake = uuid4(), uuid4(), uuid4()
    a, b, c = candidate((weak,), ref="a"), candidate((strong,), ref="b"), candidate((mistake,), ref="c")
    levels = {weak: 1, strong: 4, mistake: 3}
    assert choose_item([a, b, c], mastery_levels=levels, mistake_objectives={mistake}, recent_item_ids=set()) == c
    assert choose_item([a, b], mastery_levels=levels, mistake_objectives=set(), recent_item_ids=set()) == a
    assert choose_item([a, b], mastery_levels=levels, mistake_objectives=set(), recent_item_ids={a.id}) == b
    assert (
        choose_item(
            [a, b], mastery_levels=levels, mistake_objectives=set(), recent_item_ids=set(), required_objectives={strong}
        )
        == b
    )
    assert (
        choose_item(
            [a], mastery_levels=levels, mistake_objectives=set(), recent_item_ids=set(), required_objectives={strong}
        )
        is None
    )
    assert choose_item([], mastery_levels={}, mistake_objectives=set(), recent_item_ids=set()) is None


def test_leaks_answer_ignores_numbers_given_in_the_question() -> None:
    spec = {"answer": "12.6 or 4pi"}
    question = "Find the circumference of a circle with radius 2 cm."
    assert leaks_answer("So the answer is 12.6 cm.", spec, help_level=2, question_text=question)
    assert not leaks_answer("Use C = 2πr with r = 2.", spec, help_level=2, question_text=question)
    assert not leaks_answer("The answer is 12.6 cm.", spec, help_level=HelpLevel.FULL_SOLUTION, question_text=question)


def test_grounding_plan() -> None:
    assert grounding_plan("HIGH", citation_critical=True) == GroundingPlan(True, None, None)
    assert grounding_plan("MEDIUM", citation_critical=True).suffix == LIMITED_NOTE
    assert grounding_plan("LOW", citation_critical=True).prefix == GENERAL_LABEL
    assert grounding_plan("NONE", citation_critical=False).prefix == GENERAL_LABEL
    assert not grounding_plan("NONE", citation_critical=True).answer_allowed


def test_a_session_remembers_what_it_has_already_served() -> None:
    """Asking for the next question twice must not hand back the same one.

    Recency alone could not do this: it only knows about answers that were submitted, so pressing "next"
    without answering used to serve the same item again — which made a command-word drill useless.
    """
    first, second = uuid4(), uuid4()
    state = start_item(SessionState(), first, [OBJ])
    assert state.served_item_ids == (str(first),)
    state = start_item(state, second, [OBJ])
    assert state.served_item_ids == (str(first), str(second))
    assert SessionState.load(state.dump()).served_item_ids == state.served_item_ids


def test_served_memory_is_bounded() -> None:
    """A long session may come back to an early question rather than run out."""
    state = SessionState()
    for _ in range(SERVED_MEMORY + 5):
        state = start_item(state, uuid4(), [OBJ])
    assert len(state.served_item_ids) == SERVED_MEMORY


def test_an_already_served_item_is_skipped_while_others_remain() -> None:
    served, fresh = ItemCandidate(uuid4(), (OBJ,), 4, "a"), ItemCandidate(uuid4(), (OBJ,), 4, "b")
    chosen = choose_item([served, fresh], mastery_levels={}, mistake_objectives=set(), recent_item_ids={served.id})
    assert chosen == fresh


def test_everything_served_falls_back_rather_than_giving_up() -> None:
    """When the pool is exhausted, repeating a question beats telling her there is nothing to do."""
    only = ItemCandidate(uuid4(), (OBJ,), 4, "a")
    chosen = choose_item([only], mastery_levels={}, mistake_objectives=set(), recent_item_ids={only.id})
    assert chosen == only
