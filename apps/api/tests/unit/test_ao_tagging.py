"""AO tagging comes from the syllabus, through the subject config, never from engine code (AC-R1)."""

from __future__ import annotations

import pytest

from app.modules.subjects.config import TaughtSubjectConfig, load_all, taught_config_for


def _tagged() -> list[TaughtSubjectConfig]:
    return [c for c in load_all().values() if isinstance(c, TaughtSubjectConfig) and c.ao_tagging]


def test_sociology_declares_its_ao_rule() -> None:
    config = taught_config_for("igcse-sociology")
    assert config.ao_tagging is not None
    assert config.ao_tagging.rule_version


@pytest.mark.parametrize(
    ("source_ref", "marks", "expected"),
    [
        # Paper 1 Q1(a)(i-iii) is answered from the printed source: the syllabus says AO2 and AO3.
        ("0495/11/MJ25/Q1(a)(i)", 2, ["AO2", "AO3"]),
        ("0495/11/MJ25/Q1(a)(iii)", 6, ["AO2", "AO3"]),
        ("0495/12/MJ25/Q1(a)(ii)", 4, ["AO2", "AO3"]),
        # Short and mid-tariff parts: knowledge and application.
        ("0495/11/MJ25/Q1(b)", 2, ["AO1", "AO2"]),
        ("0495/11/MJ25/Q1(c)", 4, ["AO1", "AO2"]),
        ("0495/11/MJ25/Q2(c)", 6, ["AO1", "AO2"]),
        # Eight marks and above ask for a judgement, so analysis and evaluation joins.
        ("0495/11/MJ25/Q2(e)", 8, ["AO1", "AO2", "AO3"]),
        ("0495/11/MJ25/Q1(d)", 10, ["AO1", "AO2", "AO3"]),
        ("0495/11/MJ25/Q2(f)", 14, ["AO1", "AO2", "AO3"]),
        # A 2023 paper, set under the previous syllabus with different part letters: the tariff still holds.
        ("0495/11/MJ23/Q2(e)", 15, ["AO1", "AO2", "AO3"]),
        ("0495/11/MJ23/Q1(b)", 2, ["AO1", "AO2"]),
        # Paper 2 has no source-based part, so Q1(a) there is an ordinary short answer.
        ("0495/21/MJ25/Q1(a)(i)", 2, ["AO1", "AO2"]),
    ],
)
def test_sociology_parts_get_the_objectives_the_syllabus_states(
    source_ref: str, marks: int, expected: list[str]
) -> None:
    rule = taught_config_for("igcse-sociology").ao_tagging
    assert rule is not None
    assert rule.skills_for(marks=marks, source_ref=source_ref) == expected


def test_every_tariff_lands_somewhere() -> None:
    """A band table with a hole would silently leave items untagged."""
    for config in _tagged():
        rule = config.ao_tagging
        assert rule is not None
        for marks in range(0, 31):
            assert rule.skills_for(marks=marks, source_ref=None), f"{config.key} leaves {marks} marks untagged"


def test_the_rule_names_only_objectives_the_subject_has() -> None:
    for config in _tagged():
        rule = config.ao_tagging
        assert rule is not None
        named = {code for band in rule.bands for code in band.skills} | set(rule.source_based)
        assert named <= set(config.skill_weights), f"{config.key} tags objectives it has no weighting for"


def test_component_weightings_are_a_full_split() -> None:
    for config in load_all().values():
        if not isinstance(config, TaughtSubjectConfig):
            continue
        for component, weights in config.component_skill_weights.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{config.key} {component} weightings sum to {total}"
