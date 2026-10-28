"""Revision-note lessons (lesson_write/v5) and the Chemistry diagrams: the checks that decide what she may read."""

from __future__ import annotations

import pytest

from app.modules.learn import diagrams, lessons
from app.modules.learn.lessons import DraftExamAnswer, DraftSection, DraftTable, Excerpt, LessonDraft

BOOK = Excerpt(
    "c1",
    "Chemistry Coursebook",
    31,
    "| Subatomic particle | Relative mass | Relative charge |\n| :-- | :-- | :-- |\n"
    "| proton | 1 | +1 |\n| neutron | 1 | 0 |\n| electron | 1/1840 | -1 |\n"
    "Sodium has the electronic configuration 2,8,1 and is in Group I.",
)
PARTICLES = DraftTable(
    title="The three particles",
    columns=["Particle", "Relative mass", "Relative charge"],
    rows=[["Proton", "1", "+1"], ["Neutron", "1", "0"], ["Electron", "Negligible (1/1840)", "−1"]],
    section=1,
    sources=[1],
)


def guard(draft: LessonDraft) -> lessons.GuardedLesson:
    return lessons.guard(draft, [BOOK], example_check="none", names_need_citation=True)


def test_a_section_keeps_its_definition_points_and_tip_and_parts_are_placed_under_it() -> None:
    draft = LessonDraft(
        summary="Atoms are made of three particles.",
        introduction="Everything is built from atoms.",
        sections=[
            DraftSection(heading="Nowhere", body="Cites nothing.", sources=[]),
            DraftSection(
                heading="The particles",
                definition="An atom is the smallest particle of an element.",
                points=["Protons and neutrons sit in the nucleus.", "Electrons move in shells around it."],
                exam_tip="Give the charge with its sign.",
                sources=[1],
            ),
        ],
        tables=[PARTICLES.model_copy(update={"section": 2})],
        exam_answers=[DraftExamAnswer(question="Describe an atom.", points=["A nucleus of protons."], sources=[1])],
    )
    out = guard(draft)
    section = out.sections[0]
    assert section["points"] == ["Protons and neutrons sit in the nucleus.", "Electrons move in shells around it."]
    assert section["definition"] and section["exam_tip"] and section["body"]  # body = the points, for the voice
    assert out.tables[0]["section"] == 1  # draft section 2 is the first kept one
    assert out.exam_answers[0]["points"] == ["A nucleus of protons."] and out.introduction


def test_every_number_in_a_table_must_be_in_its_pages() -> None:
    assert lessons.guard_table(PARTICLES, [BOOK], names_need_citation=True) is not None  # "Negligible" is no name
    wrong = PARTICLES.model_copy(update={"rows": [*PARTICLES.rows[:2], ["Electron", "1/2000", "−1"]]})
    assert lessons.guard_table(wrong, [BOOK], names_need_citation=True) is None
    ragged = PARTICLES.model_copy(update={"rows": [["Proton", "1"]]})
    assert lessons.guard_table(ragged, [BOOK], names_need_citation=True) is None


def test_configurations_and_groups_in_a_table_are_checked_against_the_element_table() -> None:
    table = DraftTable(
        title="Sodium", columns=["Element", "Configuration", "Group"], rows=[["Na", "2,8,1", "I"]], sources=[1]
    )
    assert lessons.guard_table(table, [BOOK], names_need_citation=True) is not None
    wrong = table.model_copy(update={"rows": [["Na", "2,8,1", "II"]]})
    assert lessons.guard_table(wrong, [BOOK], names_need_citation=True) is None


def test_an_atom_is_drawn_from_the_element_table_and_a_false_one_is_refused() -> None:
    allowed = set(diagrams.KINDS)
    ion = diagrams.check("atom_structure", {"element": "magnesium", "mass_number": 24, "charge": 2}, allowed=allowed)
    assert (ion.data["protons"], ion.data["neutrons"], ion.data["electrons"], ion.data["shells"]) == (
        12,
        12,
        10,
        [2, 8],
    )
    for bad in ({"element": "Na", "mass_number": 40}, {"element": "Fe", "mass_number": 56}, {"element": "Xx"}):
        with pytest.raises(diagrams.DiagramError):
            diagrams.check("atom_structure", {"mass_number": 1, **bad}, allowed=allowed)


def test_a_box_of_particles_is_classified_and_its_label_must_agree() -> None:
    allowed = set(diagrams.KINDS)
    boxes = {
        "boxes": [
            {"label": "an element", "particles": [{"atoms": ["O", "O"], "count": 3}]},
            {"label": "a compound", "particles": [{"atoms": ["H", "H", "O"], "count": 3}]},
            {"label": "a mixture", "particles": [{"atoms": ["N", "N"], "count": 2}, {"atoms": ["Ar"], "count": 2}]},
        ]
    }
    drawn = diagrams.check("particle_boxes", boxes, allowed=allowed).data["boxes"]
    assert [b["classification"] for b in drawn] == ["element", "compound", "mixture"]
    assert drawn[1]["particles"][0]["formula"] == "H2O"
    backwards = {"boxes": [{"label": "a compound", "particles": [{"atoms": ["O", "O"], "count": 3}]}]}
    with pytest.raises(diagrams.DiagramError):
        diagrams.check("particle_boxes", backwards, allowed=allowed)
