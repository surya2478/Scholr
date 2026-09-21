from __future__ import annotations

from app.core.config import API_ROOT
from app.llm.config import load_roles
from app.modules.mistakes.service import MISTAKE_TYPES
from app.modules.subjects.config import SubjectConfig, TaughtSubjectConfig, load_all
from app.seed.curriculum import load_file

CURRICULUM_DIR = API_ROOT.parents[1] / "content" / "curriculum"
CURRICULUM_FILES = sorted(p for p in CURRICULUM_DIR.glob("*.yaml") if not p.name.startswith("concepts-"))


def _taught() -> list[TaughtSubjectConfig]:
    return [c for c in load_all().values() if isinstance(c, TaughtSubjectConfig)]


def _at_stage(stage: str) -> list[SubjectConfig]:
    return [c for c in load_all().values() if c.stage == stage]


def test_configs_load_and_match_seeded_subjects() -> None:
    configs = load_all()
    curriculum_codes = {load_file(p).subject["code"] for p in CURRICULUM_FILES}
    assert set(configs) == curriculum_codes


def test_mistake_categories_belong_to_the_mistake_bank() -> None:
    for config in _taught():
        assert set(config.mistake_categories) <= set(MISTAKE_TYPES), config.key


def test_evaluator_roles_exist() -> None:
    roles = load_roles().roles
    for config in _taught():
        assert config.evaluation.evaluator_role in roles
        if config.evaluation.dual_marking:
            assert config.evaluation.second_evaluator_role in roles


def test_only_a_taught_subject_declares_teaching_behaviour() -> None:
    """Retrieval, pedagogy and marking exist only where Scholr actually teaches.

    A `planned` subject has a syllabus but no questions or marking yet; an `external` one is learnt
    somewhere else entirely. Describing how either would be marked would describe behaviour that does not
    exist (docs/PHASE-3.md §1).
    """
    for stage in ("planned", "external"):
        configs = _at_stage(stage)
        assert configs, f"no subject is at stage '{stage}'"
        for config in configs:
            assert config.taught_here is False, config.key
            for field in ("retrieval", "pedagogy", "evaluation", "mistake_categories", "answer_input"):
                assert not hasattr(config, field), f"{config.key} must not carry {field}"


def test_only_a_taught_subject_can_be_practised() -> None:
    for config in load_all().values():
        assert config.can_suggest_revision == (config.stage in ("taught", "lessons", "planned")), config.key
        assert config.explains == (config.stage in ("taught", "lessons")), config.key
    assert {c.stage for c in _at_stage("external")} == {"external"}


def test_a_lessons_only_subject_carries_what_a_lesson_needs_and_nothing_to_mark_with() -> None:
    """Stage `lessons` (docs/STUDENT-APP.md D4): a corpus and worked-example rule, but no marking or questions."""
    configs = _at_stage("lessons")
    assert configs, "no subject is at stage 'lessons'"
    for config in configs:
        assert config.explains and not config.taught_here, config.key
        assert hasattr(config, "retrieval") and hasattr(config, "pedagogy"), config.key
        for field in ("evaluation", "mistake_categories", "answer_input", "question_types"):
            assert not hasattr(config, field), f"{config.key} must not carry {field}"


def test_external_subjects_are_not_on_the_igcse_path() -> None:
    """Anything on the IGCSE path is Scholr's own work, taught, explained or planned; never learnt elsewhere."""
    for config in load_all().values():
        if config.path == "IGCSE":
            assert config.stage in ("taught", "lessons", "planned"), config.key
