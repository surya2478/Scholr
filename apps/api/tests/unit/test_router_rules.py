"""Master Router rules (pure): intents, keyword matching, confidence margins."""

from __future__ import annotations

from uuid import uuid4

from app.modules.routing.rules import IndexEntry, intent_for, match, subject_aliases, words

MATHS, SOC = uuid4(), uuid4()


def entry(subject, name: str, code: str, statement: str) -> IndexEntry:  # noqa: ANN001
    return IndexEntry(
        subject_id=subject,
        subject_name=name,
        subject_aliases=subject_aliases(name, "igcse-maths" if name == "Mathematics" else "igcse-sociology"),
        objective_id=uuid4(),
        objective_code=code,
        words=frozenset(words(statement)),
        label=f"{name} {code} {statement}",
    )


INDEX = [
    entry(MATHS, "Mathematics", "2.8", "Simple interest and compound interest"),
    entry(MATHS, "Mathematics", "8.4", "Upper and lower bounds"),
    entry(SOC, "Sociology", "2.2", "How does society control us?"),
    entry(SOC, "Sociology", "4.1", "What are the different types of families?"),
]


def test_intents() -> None:
    assert intent_for("Can you explain compound interest?") == "explain"
    assert intent_for("Quiz me on families") == "practice"
    assert intent_for("I'm stuck, can I have a hint") == "help_on_attempt"
    assert intent_for("Is my answer right?") == "check_answer"
    assert intent_for("What should I study today?") == "plan"
    assert intent_for("How am I doing?") == "progress"


def test_confident_keyword_match_within_enrolled_subjects() -> None:
    found = match("how does compound interest work", INDEX)
    assert found.confident and found.candidates[0].entry.objective_code == "2.8"
    families = match("different types of families in sociology", INDEX)
    assert families.confident and families.candidates[0].entry.subject_id == SOC


def test_vague_or_unmatched_messages_are_not_confident() -> None:
    assert not match("can you help me with this", INDEX).confident
    assert match("tell me about volcanoes", INDEX).candidates == []
