"""The shared concept map is what makes Phase 3 work: without it an external class points nowhere.

AC-X5: every IIT Maths lesson reaches at least one IGCSE Maths objective, or the mapping says in `note` why
it cannot. No silent empties — a lesson with no route is a lesson the trace will quietly ignore.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.external_training import trace
from app.seed.concepts import ConceptFile, load
from app.seed.curriculum import TopicIn, load_file

CURRICULUM_DIR = Path(__file__).resolve().parents[4] / "content" / "curriculum"
CONCEPT_FILES = sorted(CURRICULUM_DIR.glob("concepts-*.yaml"))
MATHS_MAP = CURRICULUM_DIR / "concepts-maths-grade9.yaml"


def _codes(topics: list[TopicIn]) -> set[str]:
    codes: set[str] = set()
    for topic in topics:
        codes.update(o.code for o in topic.objectives)
        codes.update(_codes(topic.children))
    return codes


def _curriculum_codes(subject_code: str) -> set[str]:
    for path in sorted(CURRICULUM_DIR.glob("*.yaml")):
        if path.name.startswith("concepts-"):
            continue
        data = load_file(path)
        if data.subject["code"] == subject_code:
            return _codes(data.topics)
    raise AssertionError(f"no curriculum file for {subject_code}")


@pytest.fixture(scope="module")
def maths_map() -> ConceptFile:
    return load(MATHS_MAP)


def test_concept_files_exist() -> None:
    assert CONCEPT_FILES, "Phase 3 needs at least the Maths concept map"


@pytest.mark.parametrize("path", CONCEPT_FILES, ids=lambda p: p.name)
def test_concept_file_is_consistent(path: Path) -> None:
    data = load(path)
    names = [c.name for c in data.concepts]
    assert len(names) == len(set(names)), "concept names must be unique"
    for concept in data.concepts:
        for prerequisite, _ in concept.prerequisite_pairs():
            assert prerequisite in names, f"{concept.name} -> unknown prerequisite {prerequisite}"
            assert prerequisite != concept.name, f"{concept.name} is its own prerequisite"
        for subject_code in concept.objectives:
            assert subject_code in data.subjects, f"{concept.name} maps to unlisted subject {subject_code}"


@pytest.mark.parametrize("path", CONCEPT_FILES, ids=lambda p: p.name)
def test_mapped_objective_codes_exist(path: Path) -> None:
    data = load(path)
    known = {code: _curriculum_codes(code) for code in data.subjects}
    missing = [
        f"{concept.name}: {subject_code} {code}"
        for concept in data.concepts
        for subject_code, codes in concept.objectives.items()
        for code in codes
        if code not in known[subject_code]
    ]
    assert missing == []


@pytest.mark.parametrize("path", CONCEPT_FILES, ids=lambda p: p.name)
def test_prerequisites_have_no_cycles(path: Path) -> None:
    data = load(path)
    edges = {c.name: [p for p, _ in c.prerequisite_pairs()] for c in data.concepts}
    state: dict[str, int] = {}

    def visit(name: str, path_so_far: tuple[str, ...]) -> None:
        if state.get(name) == 1:
            raise AssertionError(f"prerequisite cycle: {' -> '.join((*path_so_far, name))}")
        if state.get(name) == 2:
            return
        state[name] = 1
        for prerequisite in edges.get(name, ()):
            visit(prerequisite, (*path_so_far, name))
        state[name] = 2

    for name in edges:
        visit(name, ())


@pytest.mark.parametrize(
    ("map_name", "external", "igcse"),
    [
        ("concepts-maths-grade9.yaml", "iit-maths", "igcse-maths"),
        ("concepts-physics-grade9.yaml", "iit-physics", "igcse-physics"),
        ("concepts-chemistry-grade9.yaml", "iit-chemistry", "igcse-chemistry"),
        ("concepts-biology-grade9.yaml", "iit-biology", "igcse-biology"),
    ],
)
def test_every_external_lesson_reaches_igcse(map_name: str, external: str, igcse: str) -> None:  # AC-X5
    """Walk the same hops the trace walks and check each lesson lands somewhere it can be reinforced."""
    data = load(CURRICULUM_DIR / map_name)
    concepts_of_lesson: dict[str, list[str]] = {}
    prerequisites: dict[str, list[str]] = {}
    igcse_objectives: dict[str, list[str]] = {}
    for concept in data.concepts:
        prerequisites[concept.name] = [p for p, _ in concept.prerequisite_pairs()]
        igcse_objectives[concept.name] = list(concept.objectives.get(igcse, []))
        for lesson in concept.objectives.get(external, []):
            concepts_of_lesson.setdefault(lesson, []).append(concept.name)

    unreachable = []
    for lesson in sorted(_curriculum_codes(external)):
        reached = set(concepts_of_lesson.get(lesson, []))
        frontier = set(reached)
        for _ in range(trace.MAX_DEPTH):
            frontier = {p for name in frontier for p in prerequisites.get(name, [])} - reached
            reached |= frontier
        if not any(igcse_objectives.get(name) for name in reached):
            unreachable.append(lesson)
    assert unreachable == [], f"every {external} lesson needs an IGCSE foundation in {map_name}"


def test_beyond_syllabus_mappings_explain_themselves(maths_map: ConceptFile) -> None:
    """Where the IIT course goes past 0580, the mapping must say what it is standing on instead."""
    explained = [c.name for c in maths_map.concepts if c.note]
    assert "Heron's formula" in explained
    assert "Polynomial evaluation and factor structure" in explained


CROSS_SUBJECT = CURRICULUM_DIR / "concepts-cross-subject.yaml"


def test_cross_subject_concepts_actually_cross_a_subject() -> None:  # AC-G2
    """A concept in this file that names only one subject is not a cross-subject link."""
    data = load(CROSS_SUBJECT)
    for concept in data.concepts:
        subjects = [code for code, codes in concept.objectives.items() if codes]
        assert len(subjects) >= 2, f"{concept.name} only reaches {subjects}"


def test_cross_subject_links_do_not_steal_concepts_from_another_file() -> None:
    """The seeder treats each file as the whole truth for the concepts it names.

    Reusing a name here would silently delete that concept's links in the file that owns it, so the names
    must be disjoint — this test is the only thing standing between a rename and quiet data loss.
    """
    owned: dict[str, str] = {}
    for path in CONCEPT_FILES:
        for concept in load(path).concepts:
            clash = owned.get(concept.name)
            assert clash is None, f"'{concept.name}' is defined in both {clash} and {path.name}"
            owned[concept.name] = path.name
