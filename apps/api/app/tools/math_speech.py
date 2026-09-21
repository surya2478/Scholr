"""Converts mathematical LaTeX expressions, units, and markdown into natural spoken English.

Kokoro 82M and other TTS engines stumble or read raw backslashes and symbols if given
unprocessed LaTeX or KaTeX markup. This deterministic pre-processor transforms formulas,
equations, exponents, fractions, and scientific units into readable phonetic prose.
"""

from __future__ import annotations

import re

# Greek symbols
_GREEK = {
    r"\pi": "pi",
    r"\theta": "theta",
    r"\alpha": "alpha",
    r"\beta": "beta",
    r"\gamma": "gamma",
    r"\delta": "delta",
    r"\Delta": "delta",
    r"\lambda": "lambda",
    r"\mu": "micro",
    r"\sigma": "sigma",
    r"\omega": "omega",
    r"\Omega": "ohms",
    "Ω": "ohms",
    "π": "pi",
    "θ": "theta",
}

# Relational and arithmetic operators
_OPERATORS = [
    (r"\\approx\b", " approximately equals "),
    (r"\\le\b|\\leq\b", " is less than or equal to "),
    (r"\\ge\b|\\geq\b", " is greater than or equal to "),
    (r"\\ne\b|\\neq\b", " does not equal "),
    (r"\\pm\b", " plus or minus "),
    (r"\\mp\b", " minus or plus "),
    (r"\\times\b", " times "),
    (r"\\cdot\b", " times "),
    (r"\\div\b", " divided by "),
    (r"\\degree\b|\\circ\b|\^\\circ", " degrees "),
    (r"°", " degrees "),
    (r"=", " equals "),
    (r"<", " is less than "),
    (r">", " is greater than "),
    (r"\+", " plus "),
    (r"-(?=\s|\d|[a-zA-Z])", " minus "),
]

# Common physical and SI units
_UNITS = [
    (r"(?:^|[\s{}])kg\s*m/s(?:\b|\s|$)", " kilogram meters per second "),
    (r"(?:^|[\s{}])m/s\s*(?:\^2|²)(?:\b|\s|$)", " meters per second squared "),
    (r"(?:^|[\s{}])m/s(?:\b|\s|$)", " meters per second "),
    (r"(?:^|[\s{}])km/h(?:\b|\s|$)", " kilometers per hour "),
    (r"(?:^|[\s{}])kg/m\s*(?:\^3|³)(?:\b|\s|$)", " kilograms per cubic meter "),
    (r"(?:^|[\s{}])J/\(kg\s*°?C\)(?:\b|\s|$)", " joules per kilogram degree Celsius "),
    (r"(?:^|[\s{}])cm\s*(?:\^3|³)(?:\b|\s|$)", " cubic centimeters "),
    (r"(?:^|[\s{}])cm\s*(?:\^2|²)(?:\b|\s|$)", " square centimeters "),
    (r"(?:^|[\s{}])m\s*(?:\^3|³)(?:\b|\s|$)", " cubic meters "),
    (r"(?:^|[\s{}])m\s*(?:\^2|²)(?:\b|\s|$)", " square meters "),
    (r"(?:^|[\s{}])mm\s*(?:\^2|²)(?:\b|\s|$)", " square millimeters "),
    (r"(?:^|[\s{}])mm(?:\b|\s|$)", " millimeters "),
    (r"(?:^|[\s{}])cm(?:\b|\s|$)", " centimeters "),
    (r"(?:^|[\s{}])km(?:\b|\s|$)", " kilometers "),
    (r"(?:^|[\s{}])kg(?:\b|\s|$)", " kilograms "),
    (r"(?:^|[\s{}])mg(?:\b|\s|$)", " milligrams "),
    (r"(?<=\d)\s*g\b", " grams "),
    (r"(?<=\d)\s*s\b", " seconds "),
    (r"(?<=\d)\s*min\b", " minutes "),
    (r"(?<=\d)\s*h\b", " hours "),
    (r"(?<=\d)\s*N\b", " newtons "),
    (r"(?<=\d)\s*J\b", " joules "),
    (r"(?<=\d)\s*W\b", " watts "),
    (r"(?<=\d)\s*Pa\b", " pascals "),
    (r"(?<=\d)\s*Hz\b", " hertz "),
    (r"(?<=\d)\s*V\b", " volts "),
    (r"(?<=\d)\s*A\b", " amps "),
]


def _replace_fractions(text: str) -> str:
    """Convert \\frac{num}{den} to 'num over den' recursively."""
    pattern = re.compile(r"\\frac\{([^{}]+)\}\{([^{}]+)\}")
    while pattern.search(text):
        text = pattern.sub(r"\1 over \2", text)
    return text


def _replace_roots(text: str) -> str:
    """Convert \\sqrt{expr} and \\sqrt[n]{expr} to spoken English."""
    text = re.sub(r"\\sqrt\[(\d+)\]\{([^{}]+)\}", r"the \1th root of \2", text)
    pattern = re.compile(r"\\sqrt\{([^{}]+)\}")
    while pattern.search(text):
        text = pattern.sub(r"the square root of \1", text)
    return text


def _replace_powers(text: str) -> str:
    """Convert exponents and powers like x^2, x^3, y^{-1} to speech."""
    # Special cases: squared and cubed
    text = re.sub(r"(\w+)\^2\b", r"\1 squared", text)
    text = re.sub(r"(\w+)\^\{2\}", r"\1 squared", text)
    text = re.sub(r"(\w+)\^3\b", r"\1 cubed", text)
    text = re.sub(r"(\w+)\^\{3\}", r"\1 cubed", text)

    # General powers: x^{n} or x^n
    text = re.sub(r"(\w+)\^\{([^{}]+)\}", r"\1 to the power of \2", text)
    text = re.sub(r"(\w+)\^([a-zA-Z0-9]+)", r"\1 to the power of \2", text)
    return text


def _clean_latex(expr: str) -> str:
    """Translate one LaTeX math expression into natural spoken prose."""
    # Unwrap \text{...} or \mathrm{...}
    expr = re.sub(r"\\(?:text|mathrm|mathbf)\{([^{}]+)\}", r" \1 ", expr)

    # Clean LaTeX spacing escapes like "\ ", "\,", "\;", "\quad"
    expr = re.sub(r"\\[ ,;]|\\quad|\\qquad", " ", expr)

    # Handle fractions & roots
    expr = _replace_fractions(expr)
    expr = _replace_roots(expr)

    # Physical units
    for pattern, replacement in _UNITS:
        expr = re.sub(pattern, replacement, expr)

    # Greek characters
    for sym, word in _GREEK.items():
        expr = expr.replace(sym, f" {word} ")

    # Operators
    for pattern, replacement in _OPERATORS:
        expr = re.sub(pattern, replacement, expr)

    # Powers
    expr = _replace_powers(expr)

    # Clean leftover LaTeX control words
    expr = re.sub(r"\\[a-zA-Z]+", "", expr)
    expr = re.sub(r"[{}]", "", expr)
    return expr


def math_to_speech(text: str) -> str:
    """Converts a lesson text containing markdown and LaTeX into smooth English speech."""
    # Remove citation brackets like [1, 2] or [3]
    text = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", text)

    # Remove markdown headers (###, ##, #)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold / italic markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # Convert display math $$...$$
    def _display_math(match: re.Match) -> str:
        return f" , {_clean_latex(match.group(1))} , "

    text = re.sub(r"\$\$(.*?)\$\$", _display_math, text, flags=re.DOTALL)

    # Convert inline math $...$
    def _inline_math(match: re.Match) -> str:
        return f" {_clean_latex(match.group(1))} "

    text = re.sub(r"\$([^$]+)\$", _inline_math, text)

    # Standardize whitespace and punctuation pauses
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.?!])", r"\1", text)
    text = re.sub(r"([,.?!]){2,}", r"\1", text)

    return text.strip()
