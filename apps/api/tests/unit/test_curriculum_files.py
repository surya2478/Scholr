"""Committed curriculum files must parse and stay internally consistent."""

from pathlib import Path

import pytest

from app.modules.subjects.config import config_for
from app.seed.curriculum import CurriculumFile, TopicIn, load_file

CURRICULUM_DIR = Path(__file__).resolve().parents[4] / "content" / "curriculum"
# concepts-*.yaml is the shared concept map, not a curriculum (see tests/unit/test_concept_map.py).
CURRICULUM_FILES = sorted(p for p in CURRICULUM_DIR.glob("*.yaml") if not p.name.startswith("concepts-"))


def _objective_codes(topics: list[TopicIn]) -> list[str]:
    codes: list[str] = []
    for topic in topics:
        codes.extend(o.code for o in topic.objectives)
        codes.extend(_objective_codes(topic.children))
    return codes


@pytest.mark.parametrize("path", CURRICULUM_FILES, ids=lambda p: p.name)
def test_curriculum_file_is_valid(path: Path) -> None:
    data: CurriculumFile = load_file(path)
    codes = _objective_codes(data.topics)
    assert codes, "curriculum must define learning objectives"
    assert len(codes) == len(set(codes)), "objective codes must be unique within a subject"


@pytest.mark.parametrize("path", CURRICULUM_FILES, ids=lambda p: p.name)
def test_a_taught_subject_has_a_verified_syllabus(path: Path) -> None:
    """You cannot teach to a syllabus nobody has checked.

    Verification and stage are separate: 0625, 0620 and 0610 were verified against their official PDFs on
    16 Sep 2026 but stay `planned` until the rest of the engine exists for them. The rule only runs one way —
    a `taught` subject must be verified.
    """
    data: CurriculumFile = load_file(path)
    config = config_for(data.subject["code"])
    if not config.taught_here:
        return
    assert {s.code for s in data.skills} >= {"AO1", "AO2"}
    assert data.syllabus.verification_status == "verified"


@pytest.mark.parametrize("path", CURRICULUM_FILES, ids=lambda p: p.name)
def test_an_external_curriculum_is_never_claimed_as_verified(path: Path) -> None:
    """The IIT Foundation provider publishes no syllabus document, so nothing about it can be verified."""
    data: CurriculumFile = load_file(path)
    if config_for(data.subject["code"]).stage == "external":
        assert data.syllabus.verification_status == "unverified", data.subject["code"]


@pytest.mark.parametrize("path", CURRICULUM_FILES, ids=lambda p: p.name)
def test_every_curriculum_has_a_subject_config(path: Path) -> None:
    data: CurriculumFile = load_file(path)
    assert config_for(data.subject["code"]).key == data.subject["config_key"]


def test_expected_subjects_present() -> None:
    subjects = {load_file(p).subject["code"] for p in CURRICULUM_FILES}
    assert subjects == {
        "igcse-maths",
        "igcse-sociology",
        "igcse-physics",
        "igcse-chemistry",
        "igcse-biology",
        "iit-maths",
        "iit-physics",
        "iit-chemistry",
        "iit-biology",
    }


def test_maths_term1_areas_match_school_planner() -> None:
    maths = load_file(CURRICULUM_DIR / "igcse-maths-0580.yaml")
    names = [t.name for t in maths.topics[:4]]
    assert names == ["Number", "Algebra and graphs", "Coordinate geometry", "Geometry"]
