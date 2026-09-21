"""Typed answers from the MathLive maths keyboard arrive as LaTeX; the deterministic tools must read them."""

from __future__ import annotations

import pytest
import sympy

from app.tools.math_sympy import normalize, parse_math

x = sympy.Symbol("x")


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        ("\\frac{3}{4}", sympy.Rational(3, 4)),
        ("$\\frac{3}{4}$", sympy.Rational(3, 4)),
        ("\\frac{\\sqrt{2}}{2}", sympy.sqrt(2) / 2),
        ("\\sqrt[3]{8}", sympy.Integer(2)),
        ("2\\times10^{3}", sympy.Integer(2000)),
        ("4\\cdot\\pi", 4 * sympy.pi),
        ("\\left(x+1\\right)^{2}", (x + 1) ** 2),
    ],
)
def test_mathlive_latex_parses(latex: str, expected: sympy.Expr) -> None:
    assert sympy.simplify(parse_math(latex) - expected) == 0


def test_units_degrees_currency_and_percent_are_unwrapped() -> None:
    assert normalize("35^{\\circ}") == "35"
    assert normalize("35^\\circ") == "35"
    assert normalize("12.6\\mathrm{cm}") == "12.6cm"
    assert normalize("12.6\\text{ cm}") == "12.6 cm"
    assert normalize("\\$12.50") == "12.50"
    assert normalize("15\\%") == "15%"
