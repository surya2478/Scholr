from __future__ import annotations

import pytest

from app.modules.knowledge.ocr_compare import escape_damage, unicode_leaks
from app.modules.knowledge.postprocess import apply_postprocess, repair_json_escapes, unicode_math_to_latex


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The angle is 85°.", "The angle is $85^\\circ$."),
        ("Area 378 000 km² in total", "Area 378 000 km$^{2}$ in total"),
        ("Work out 3×4 now", "Work out 3$\\times$4 now"),
        ("√50 is irrational", "$\\sqrt{50}$ is irrational"),
        ("Use π and ½", "Use $\\pi$ and $\\frac{1}{2}$"),
        ("CO₂ levels", "CO$_{2}$ levels"),
        ("Angles 30°×2", "Angles $30^\\circ\\times$2"),
    ],
)
def test_unicode_outside_maths_becomes_latex(text: str, expected: str) -> None:
    converted = unicode_math_to_latex(text)
    assert converted == expected
    assert unicode_leaks(converted) == 0


def test_existing_latex_is_untouched_and_superscript_joins_it() -> None:
    assert unicode_math_to_latex("Solve $x^2 + 3x = 10$ today") == "Solve $x^2 + 3x = 10$ today"
    assert unicode_math_to_latex("so $x$² is positive") == "so $x^{2}$ is positive"
    assert unicode_math_to_latex("$$a + b$$ and 45°") == "$$a + b$$ and $45^\\circ$"


def test_symbol_next_to_existing_maths_does_not_create_display_delimiters() -> None:
    converted = unicode_math_to_latex("$3$×$4$")
    assert "$$" not in converted
    assert unicode_leaks(converted) == 0


def test_unbalanced_dollar_text_is_left_alone() -> None:
    assert unicode_math_to_latex("costs $5 and 30°") == "costs $5 and 30°"


def test_json_escape_damage_is_repaired() -> None:
    damaged = "$(4 \\div 100) \times 8$ and $\frac{1}{2}$ and $\\left(x\right)$"  # \t, \f, \r decoded by JSON
    repaired = repair_json_escapes(damaged)
    assert repaired == "$(4 \\div 100) \\times 8$ and $\\frac{1}{2}$ and $\\left(x\\right)$"
    assert escape_damage(repaired) == 0
    assert repair_json_escapes("line one\n\tindented note") == "line one\n\tindented note"


def test_apply_postprocess_steps() -> None:
    assert apply_postprocess("85°", []) == "85°"
    assert apply_postprocess("85°", ["unicode_math_to_latex"]) == "$85^\\circ$"
