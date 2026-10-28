"""Unit tests for lesson v6 (coaching center framework & NotebookLM podcast dialogue)."""

from __future__ import annotations

from app.modules.learn import lessons
from app.modules.learn.lessons import (
    DraftExample,
    DraftPodcastTurn,
    DraftSection,
    Excerpt,
    LessonDraft,
)

BOOK = Excerpt(
    "c1",
    "Physics Coursebook",
    42,
    "Force equals mass times acceleration ($F = ma$). "
    "A force of 10 N acts on a 2 kg mass, giving an acceleration of 5 m/s^2.",
)


def guard(draft: LessonDraft) -> lessons.GuardedLesson:
    return lessons.guard(draft, [BOOK], example_check="sympy", names_need_citation=False, answer_units=True)


def test_coaching_center_fields_are_kept_in_guarded_lesson() -> None:
    draft = LessonDraft(
        summary="Newton's second law connects force, mass, and acceleration.",
        introduction="When you push an object, its speed changes depending on how heavy it is.",
        sections=[
            DraftSection(
                heading="Newton's Second Law",
                mental_model="Imagine pushing an empty shopping trolley versus a full one with the same effort.",
                definition="Resultant force is proportional to the rate of change of momentum.",
                formula_notes=(
                    "$F = ma$, where $F$ is in Newtons (N), $m$ in kg, and $a$ in $\\text{m/s}^2$. "
                    "Valid only for constant mass."
                ),
                points=["Doubling the force doubles the acceleration.", "Mass resists change in motion."],
                exam_tip="Always check that mass is converted into kilograms.",
                sources=[1],
            )
        ],
        worked_examples=[
            DraftExample(
                level="standard",
                section=1,
                problem="Calculate the acceleration of a 2 kg block pushed with a 10 N resultant force.",
                strategy=(
                    "Identify given: $m = 2\\text{ kg}$, $F = 10\\text{ N}$. Goal: acceleration $a$. "
                    "Apply $F = ma \\implies a = F/m$."
                ),
                steps=["$a = F / m$", "$a = 10 / 2$", "$a = 5$"],
                final_answer="5",
                answer_expression="10/2",
                unit="m/s^2",
                coaching_takeaway="Check units: Newtons divided by kilograms directly yields $\\text{m/s}^2$.",
                sources=[1],
            )
        ],
        podcast_script=[
            DraftPodcastTurn(speaker="Maya", text="So why doesn't a heavy truck speed up as quickly as a sports car?"),
            DraftPodcastTurn(
                speaker="Leo",
                text="Because mass represents inertia—its built-in resistance to acceleration!",
            ),
        ],
    )

    out = guard(draft)
    assert len(out.sections) == 1
    sec = out.sections[0]
    assert "trolley" in sec["mental_model"]
    assert "constant mass" in sec["formula_notes"]
    assert "kilograms" in sec["exam_tip"]

    assert len(out.worked_examples) == 1
    ex = out.worked_examples[0]
    assert "Identify given" in ex["strategy"]
    assert "Check units" in ex["coaching_takeaway"]
    assert ex["final_answer"] == "5"

    assert len(out.podcast_script) == 2
    assert out.podcast_script[0]["speaker"] == "Maya"
    assert "inertia" in out.podcast_script[1]["text"]
