from uuid import uuid4

from app.modules.routing.resolver import RoutingContext, resolve

INDEX = {
    "igcse-maths": ["quadratic", "equation", "gradient", "simultaneous equations", "factorise", "sequence"],
    "igcse-sociology": ["socialisation", "family", "sampling frame", "validity", "marxist", "education"],
}
ENROLLED = ["igcse-maths", "igcse-sociology"]


def test_study_assessment_locks_and_disables_tutoring() -> None:
    ctx = RoutingContext(
        ENROLLED,
        active_assessment_id=uuid4(),
        active_assessment_kind="baseline",
        active_assessment_subject_code="igcse-maths",
    )
    route = resolve(ctx, "can you give me a hint?", INDEX)
    assert route.source == "assessment_lock"
    assert not route.tutoring_allowed


def test_practice_assessment_allows_tutoring() -> None:
    ctx = RoutingContext(
        ENROLLED,
        active_assessment_id=uuid4(),
        active_assessment_kind="practice",
        active_assessment_subject_code="igcse-maths",
    )
    assert resolve(ctx, "hint please", INDEX).tutoring_allowed


def test_session_context_wins_without_llm() -> None:
    objective = uuid4()
    ctx = RoutingContext(ENROLLED, session_subject_code="igcse-maths", session_objective_id=objective)
    route = resolve(ctx, "what does Marxist mean?", INDEX)
    assert route.source == "session"
    assert route.subject_code == "igcse-maths"
    assert route.objective_id == objective


def test_keyword_rules_route_clear_questions() -> None:
    route = resolve(RoutingContext(ENROLLED), "How do I solve simultaneous equations?", INDEX)
    assert route.source == "rules"
    assert route.subject_code == "igcse-maths"


def test_ambiguous_text_needs_classifier() -> None:
    route = resolve(RoutingContext(ENROLLED), "Is the equation for family size valid?", INDEX)
    assert route.source == "needs_classifier"
    assert set(route.candidates) == set(ENROLLED)


def test_no_matches_needs_classifier() -> None:
    route = resolve(RoutingContext(ENROLLED), "help me with my homework", INDEX)
    assert route.source == "needs_classifier"


def test_only_enrolled_subjects_considered() -> None:
    route = resolve(RoutingContext(["igcse-sociology"]), "quadratic equation", INDEX)
    assert route.source == "needs_classifier"
