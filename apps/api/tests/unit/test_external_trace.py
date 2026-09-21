"""Tracing an external-class weakness to IGCSE work (AC-X6 determinism, AC-X7 prerequisites, AC-X8 secure)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.modules.external_training import trace

TODAY = date(2026, 9, 16)


def _id(n: int) -> UUID:
    return UUID(int=n, version=4)


# A tiny graph: the class taught HERON, which rests on TRIANGLE_AREA, which rests on AREA_BASICS.
LESSON = _id(1)
HERON, TRIANGLE_AREA, AREA_BASICS, UNRELATED = _id(10), _id(11), _id(12), _id(13)
# One IGCSE objective per concept, plus a sibling of Heron's own concept.
OBJ_HERON, OBJ_TRIANGLE, OBJ_BASICS, OBJ_SIBLING = _id(20), _id(21), _id(22), _id(23)

GRAPH = trace.ConceptGraph(
    concepts_of_objective={LESSON: (HERON,)},
    prerequisites={HERON: ((TRIANGLE_AREA, 1.0),), TRIANGLE_AREA: ((AREA_BASICS, 1.0),)},
    objectives_of_concept={
        HERON: (OBJ_HERON, OBJ_SIBLING),
        TRIANGLE_AREA: (OBJ_TRIANGLE,),
        AREA_BASICS: (OBJ_BASICS,),
        UNRELATED: (_id(99),),
    },
    concept_names={HERON: "Heron's formula", TRIANGLE_AREA: "Area of a triangle", AREA_BASICS: "Perimeter basics"},
)
WEAKNESS = [trace.Weakness(objective_id=LESSON, occurred_on=TODAY, severity=1.0)]


def test_need_rises_as_mastery_falls() -> None:
    assert trace.need(trace.Standing(level=1)) > trace.need(trace.Standing(level=3))
    assert trace.need(trace.Standing(level=3, open_mistakes=2)) > trace.need(trace.Standing(level=3))
    assert trace.need(trace.Standing(level=None)) > trace.need(trace.Standing(level=3))


def test_need_is_capped_at_one() -> None:
    assert trace.need(trace.Standing(level=0, open_mistakes=5, retention_risk="high")) == 1.0


def test_secure_objectives_are_never_targets() -> None:  # AC-X8
    standings = dict.fromkeys(
        (OBJ_HERON, OBJ_TRIANGLE, OBJ_BASICS, OBJ_SIBLING), trace.Standing(level=4, open_mistakes=0)
    )
    assert trace.targets(WEAKNESS, GRAPH, standings, today=TODAY) == []


def test_a_mastered_objective_returns_when_something_is_open() -> None:
    standings = {OBJ_HERON: trace.Standing(level=4, open_mistakes=1)}
    found = trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)
    assert [t.objective_id for t in found if t.objective_id == OBJ_HERON]


def test_a_weaker_prerequisite_is_reinforced_before_what_stands_on_it() -> None:  # AC-X7
    standings = {
        OBJ_HERON: trace.Standing(level=3),
        OBJ_SIBLING: trace.Standing(level=3),
        OBJ_TRIANGLE: trace.Standing(level=2),
        OBJ_BASICS: trace.Standing(level=1),
    }
    order = [t.objective_id for t in trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)]
    assert order.index(OBJ_BASICS) < order.index(OBJ_TRIANGLE) < order.index(OBJ_HERON)


def test_with_nothing_to_separate_them_the_class_topic_comes_first() -> None:
    """Depth alone is not evidence: two hops down is not a better answer than the idea she just met."""
    standings = dict.fromkeys((OBJ_HERON, OBJ_SIBLING, OBJ_TRIANGLE, OBJ_BASICS), trace.Standing(level=2))
    order = [t.objective_id for t in trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)]
    assert order.index(OBJ_HERON) < order.index(OBJ_TRIANGLE) < order.index(OBJ_BASICS)


def test_a_secure_prerequisite_steps_aside_for_the_weak_concept() -> None:
    standings = {
        OBJ_HERON: trace.Standing(level=1),
        OBJ_SIBLING: trace.Standing(level=1),
        OBJ_TRIANGLE: trace.Standing(level=4),
        OBJ_BASICS: trace.Standing(level=4),
    }
    found = trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)
    assert {t.objective_id for t in found} == {OBJ_HERON, OBJ_SIBLING}


def test_walk_stops_at_max_depth() -> None:
    deep = _id(14)
    graph = trace.ConceptGraph(
        concepts_of_objective={LESSON: (HERON,)},
        prerequisites={
            HERON: ((TRIANGLE_AREA, 1.0),),
            TRIANGLE_AREA: ((AREA_BASICS, 1.0),),
            AREA_BASICS: ((deep, 1.0),),
        },
        objectives_of_concept={deep: (_id(30),), HERON: (OBJ_HERON,)},
    )
    found = trace.targets(WEAKNESS, graph, {}, today=TODAY)
    assert _id(30) not in {t.objective_id for t in found}


def test_an_older_class_weighs_less() -> None:
    standings = {OBJ_HERON: trace.Standing(level=2)}
    fresh = trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)[0]
    old = trace.targets(
        [trace.Weakness(objective_id=LESSON, occurred_on=date(2026, 8, 5), severity=1.0)],
        GRAPH,
        standings,
        today=TODAY,
    )[0]
    assert old.priority < fresh.priority


def test_the_same_inputs_always_give_the_same_list() -> None:  # AC-X6
    standings = {OBJ_HERON: trace.Standing(level=2), OBJ_SIBLING: trace.Standing(level=2)}
    runs = [trace.targets(WEAKNESS, GRAPH, standings, today=TODAY) for _ in range(5)]
    assert all(run == runs[0] for run in runs)


def test_a_target_is_never_the_external_lesson_itself() -> None:  # AC-X10
    found = trace.targets(WEAKNESS, GRAPH, {}, today=TODAY)
    assert LESSON not in {t.objective_id for t in found}


def test_limit_keeps_the_strongest() -> None:
    standings = dict.fromkeys((OBJ_HERON, OBJ_SIBLING, OBJ_TRIANGLE, OBJ_BASICS), trace.Standing(level=2))
    full = trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)
    assert trace.targets(WEAKNESS, GRAPH, standings, today=TODAY, limit=2) == full[:2]


def test_zero_severity_traces_nothing() -> None:
    quiet = [trace.Weakness(objective_id=LESSON, occurred_on=TODAY, severity=0.0)]
    assert trace.targets(quiet, GRAPH, {}, today=TODAY) == []


def test_one_concept_cannot_fill_the_list() -> None:
    """A broad foundation concept must not crowd out the idea the class was actually about."""
    many = tuple(_id(40 + n) for n in range(5))
    graph = trace.ConceptGraph(
        concepts_of_objective={LESSON: (HERON,)},
        prerequisites={HERON: ((AREA_BASICS, 1.0),)},
        objectives_of_concept={HERON: (OBJ_HERON,), AREA_BASICS: many},
        concept_names={HERON: "Heron's formula", AREA_BASICS: "Perimeter basics"},
    )
    found = trace.targets(WEAKNESS, graph, {}, today=TODAY)
    assert sum(t.concept_id == AREA_BASICS for t in found) == trace.PER_CONCEPT_LIMIT
    assert OBJ_HERON in {t.objective_id for t in found}


def test_a_tie_keeps_the_concept_closest_to_the_class() -> None:
    """The same objective is reachable at two depths; float noise must not silently prefer the deeper one."""
    standings = {OBJ_HERON: trace.Standing(level=2)}
    graph = trace.ConceptGraph(
        concepts_of_objective={LESSON: (HERON,)},
        prerequisites={HERON: ((TRIANGLE_AREA, 1.0),)},
        objectives_of_concept={HERON: (OBJ_HERON,), TRIANGLE_AREA: (OBJ_HERON,)},
        concept_names={HERON: "Heron's formula", TRIANGLE_AREA: "Area of a triangle"},
    )
    found = trace.targets(WEAKNESS, graph, standings, today=TODAY)
    assert [(t.concept_name, t.depth) for t in found] == [("Heron's formula", 0)]


def test_each_class_gets_a_turn() -> None:
    """With several courses being logged, the loudest class must not hide all the others."""
    other_lesson, other_concept = _id(2), _id(15)
    many = tuple(_id(50 + n) for n in range(5))
    graph = trace.ConceptGraph(
        concepts_of_objective={LESSON: (HERON,), other_lesson: (other_concept,)},
        prerequisites={},
        objectives_of_concept={HERON: (OBJ_HERON, OBJ_SIBLING), other_concept: many},
        concept_names={HERON: "Heron's formula", other_concept: "Something else"},
    )
    weaknesses = [
        trace.Weakness(objective_id=other_lesson, occurred_on=TODAY, severity=1.0),
        trace.Weakness(objective_id=LESSON, occurred_on=TODAY, severity=0.9),
    ]
    found = trace.targets(weaknesses, graph, {}, today=TODAY, limit=4)
    assert [t.from_objective_id for t in found] == [other_lesson, LESSON, other_lesson, LESSON]


def test_one_class_alone_is_not_throttled() -> None:
    """The round-robin must not become a cap when only one class has been logged."""
    standings = dict.fromkeys((OBJ_HERON, OBJ_SIBLING, OBJ_TRIANGLE, OBJ_BASICS), trace.Standing(level=2))
    found = trace.targets(WEAKNESS, GRAPH, standings, today=TODAY)
    assert len(found) == 4
