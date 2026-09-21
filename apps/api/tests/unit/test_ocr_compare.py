from __future__ import annotations

import pytest

from app.modules.knowledge.ocr_compare import (
    PageComparison,
    compare,
    content_tokens,
    escape_damage,
    math_tokens,
    summarise,
    unicode_leaks,
)

PAGE = """# 2.4 Simplifying fractions

KEY TERMS: a fraction is in its simplest form when $\\frac{a}{b}$ has no common factor.

[Figure: a bar split into four equal parts]

Find the median of $7, 6, 2, 3, 1$.

$$x^{2} + 3x = 10$$
"""


def test_identical_pages_score_one() -> None:
    result = compare(12, PAGE, PAGE)
    assert (result.content_f1, result.word_f1, result.math_f1, result.math_recall) == (1.0, 1.0, 1.0, 1.0)
    assert (result.unicode_leaks, result.escape_damage) == (0, 0)


def test_figure_descriptions_are_ignored() -> None:
    reworded = PAGE.replace("a bar split into four equal parts", "rectangle divided into quarters")
    assert compare(12, PAGE, reworded).content_f1 == 1.0


def test_content_is_notation_agnostic_but_leaks_are_counted() -> None:
    unicode_style = PAGE.replace("$7, 6, 2, 3, 1$", "7, 6, 2, 3, 1").replace("$$x^{2} + 3x = 10$$", "x² + 3x = 10")
    result = compare(12, PAGE, unicode_style)
    assert result.content_f1 == 1.0
    assert result.unicode_leaks == 1
    assert content_tokens("½") == content_tokens("$\\frac{1}{2}$")


def test_math_recall_catches_single_symbol_errors_that_content_misses() -> None:
    reference = "a $\\sqrt[7]{2187}$ b $4^3 \\div \\sqrt[4]{16}$ c $5^n = 3125$"
    candidate = "a $\\sqrt[3]{2187}$ b $4^3 + \\sqrt[4]{16}$ c $5^n = 3125$"
    result = compare(83, reference, candidate)
    assert result.content_f1 > 0.8
    assert result.math_recall == pytest.approx(1 / 3, abs=1e-3)


def test_segment_spelling_variants_still_match() -> None:
    assert compare(1, "$\\dfrac{1}{2} \\leq x$", "$\\frac12\\le x$").math_recall == 1.0


def test_latex_spelling_variants_are_equivalent() -> None:
    assert math_tokens("$\\dfrac{a}{b}$") == math_tokens("$\\frac{a}{b}$")
    assert unicode_leaks("angle $85^\\circ$ and 30°") == 1


def test_json_escape_damage_is_detected() -> None:
    assert escape_damage("$(4 \text{ } 100) \times 8$") == 2  # \t and \f decoded as control characters
    assert escape_damage("$(4 \\div 100) \\times 8$") == 0
    assert escape_damage("indented\n\tnot a command? 12") == 0


def row(page: int, content: float, **overrides: object) -> PageComparison:
    values: dict[str, object] = {
        "page_number": page,
        "content_f1": content,
        "word_f1": content,
        "math_f1": 0.9,
        "math_recall": 0.9,
        "unicode_leaks": 0,
        "escape_damage": 0,
        "reference_math_segments": 10,
        "candidate_math_segments": 10,
    }
    values.update(overrides)
    return PageComparison(**values)  # type: ignore[arg-type]


def test_summary_verdict() -> None:
    good = [row(i, 0.97) for i in range(5)]
    assert summarise(good).verdict == "candidate_ok"
    assert summarise([*good, row(9, 0.6)]).verdict == "review"
    assert summarise([*good, row(9, 0.97, unicode_leaks=2)]).verdict == "review"
    assert summarise([*good, row(9, 0.97, escape_damage=1)]).verdict == "review"
    assert summarise([row(i, 0.97, candidate_math_segments=3) for i in range(5)]).verdict == "review"
    with pytest.raises(ValueError):
        summarise([])
