"""Deterministic clean-up of OCR Markdown, enabled per source in its manifest (``ocr_postprocess``).

``unicode_math_to_latex``: low-cost OCR models occasionally leave Unicode maths (85°, km², 3×4, π) outside
``$...$`` despite the prompt. Only text outside existing maths is touched; existing LaTeX is never rewritten.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from app.llm.text_repair import repair_json_escapes

__all__ = ["POSTPROCESSORS", "apply_postprocess", "repair_json_escapes", "unicode_math_to_latex"]

_MATH = re.compile(r"(\$\$.+?\$\$|\$[^$\n]+?\$)", re.DOTALL)
_SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUB = "₀₁₂₃₄₅₆₇₈₉"
_TO_DIGITS = str.maketrans(_SUPER + _SUB, "0123456789" * 2)

# A superscript directly after existing inline maths joins that maths: $x$² -> $x^{2}$
_SUPER_AFTER_MATH = re.compile(r"\$([^$\n]+?)\$([" + _SUPER + r"]+)")
_DEGREES = re.compile(r"(\d+(?:\.\d+)?)\s*°")
_BASE_SUPER = re.compile(r"([A-Za-z0-9)\]])([" + _SUPER + r"]+)")
_BASE_SUB = re.compile(r"([A-Za-z0-9])([" + _SUB + r"]+)")
_ROOT = re.compile(r"√\s*(\d+(?:\.\d+)?|[A-Za-z])")
_SYMBOLS = {
    "×": r"\times",
    "÷": r"\div",
    "π": r"\pi",
    "≤": r"\le",
    "≥": r"\ge",
    "≠": r"\ne",
    "≈": r"\approx",
    "±": r"\pm",
    "∠": r"\angle",
    "½": r"\frac{1}{2}",
    "¼": r"\frac{1}{4}",
    "¾": r"\frac{3}{4}",
    "⅓": r"\frac{1}{3}",
    "⅔": r"\frac{2}{3}",
    "√": r"\sqrt{\ }",
    "°": r"^\circ",
}


def _digits(text: str) -> str:
    return text.translate(_TO_DIGITS)


def _convert_plain(text: str) -> str:
    """Convert Unicode maths in a stretch of text that contains no ``$``."""
    out = _DEGREES.sub(lambda m: f"${m.group(1)}^\\circ$", text)
    out = _BASE_SUPER.sub(lambda m: f"{m.group(1)}$^{{{_digits(m.group(2))}}}$", out)
    out = _BASE_SUB.sub(lambda m: f"{m.group(1)}$_{{{_digits(m.group(2))}}}$", out)
    out = _ROOT.sub(lambda m: f"$\\sqrt{{{m.group(1)}}}$", out)
    for char, latex in _SYMBOLS.items():
        out = out.replace(char, f"${latex}$")
    out = re.sub("[" + _SUPER + "]+", lambda m: f"$^{{{_digits(m.group(0))}}}$", out)
    out = re.sub("[" + _SUB + "]+", lambda m: f"$_{{{_digits(m.group(0))}}}$", out)
    return out.replace("$$", "")  # merge adjacent new inline segments: $85^\circ$$\times$ -> $85^\circ\times$


def unicode_math_to_latex(markdown: str) -> str:
    text = _SUPER_AFTER_MATH.sub(lambda m: f"${m.group(1)}^{{{_digits(m.group(2))}}}$", markdown)
    parts = _MATH.split(text)
    for i in range(0, len(parts), 2):  # even indexes are outside maths
        if "$" in parts[i]:
            continue  # unbalanced dollar sign: leave untouched rather than guess
        converted = _convert_plain(parts[i])
        if converted != parts[i]:
            if i > 0 and converted.startswith("$"):
                converted = " " + converted
            if i < len(parts) - 1 and converted.endswith("$"):
                converted += " "
        parts[i] = converted
    return "".join(parts)


POSTPROCESSORS: dict[str, Callable[[str], str]] = {
    "unicode_math_to_latex": unicode_math_to_latex,
    "repair_json_escapes": repair_json_escapes,
}


def apply_postprocess(markdown: str, steps: Sequence[str]) -> str:
    for step in steps:
        markdown = POSTPROCESSORS[step](markdown)
    return markdown
