"""Parametric templates: every generated item's printed answer is SymPy-verified by the real answer checker (AC-E1)."""

from __future__ import annotations

import pytest

from app.modules.assessment.templates import TemplateSpec, generate, load_templates
from app.tools.answer_check import check_final_answer

TEMPLATES = load_templates("igcse_maths_0580").templates


@pytest.mark.parametrize("spec", TEMPLATES, ids=lambda s: s.id)
def test_every_template_generates_verified_items(spec: TemplateSpec) -> None:
    for seed in range(8):
        item = generate(spec, seed)
        assert item.verified, (item.source_ref, item.issues)
        assert item.answer_spec["sympy_verified"] is True
        assert "{" not in item.stem and "{" not in item.mark_scheme
        assert check_final_answer(item.answer, item.answer_spec).status == "correct"


def test_generation_is_deterministic_and_wrong_answers_are_not_accepted() -> None:
    spec = next(t for t in TEMPLATES if t.id == "compound_interest_value")
    first, again = generate(spec, 3), generate(spec, 3)
    assert (first.stem, first.answer) == (again.stem, again.answer)
    assert check_final_answer("1", first.answer_spec).status != "correct"


def test_broken_template_is_not_verified() -> None:
    broken = TemplateSpec(
        id="broken",
        objective="1.1",
        marks=1,
        difficulty=1,
        command_word="Find",
        stem="Find {a}.",
        params={"a": [0]},
        exact="1/a",
        accuracy="exact",
        mark_scheme="B1 {answer}",
    )
    item = generate(broken, 0)
    assert not item.verified and item.answer_spec["sympy_verified"] is False
