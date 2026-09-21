"""Units of measurement, checked with Pint (the stack's units tool, introduced with the Physics slice).

Used to accept or reject the unit a Physics worked example prints (docs/STUDENT-APP.md §10). Deterministic: a
unit is valid if Pint can parse it after the textbook spellings below are normalised.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pint

# Textbook and LaTeX spellings -> Pint's. Order matters: "°C" before "°".
_SPELLINGS = (
    ("\\Omega", "ohm"),
    ("Ω", "ohm"),
    ("\\mu", "u"),
    ("μ", "u"),
    ("µ", "u"),
    ("°C", "degC"),
    ("^\\circ C", "degC"),
    ("^{\\circ}C", "degC"),
    ("°", "deg"),
    ("²", "^2"),
    ("³", "^3"),
    ("·", "*"),
    ("×", "*"),
    ("\\cdot", "*"),
    ("\\,", " "),
)
_TEXT_WRAPPER = re.compile(r"\\(?:text|mathrm)\{([^}]*)\}")
_BRACED_POWER = re.compile(r"\^\{([^}]*)\}")
# A space or a glued degree sign between two unit symbols means multiplication: "kg m", "kg°C".
_IMPLIED_PRODUCT = re.compile(r"(?<=[A-Za-z0-9)])\s+(?=[A-Za-z(])")
NO_UNIT = frozenset({"", "none", "no unit", "dimensionless", "-"})


@lru_cache(maxsize=1)
def _registry() -> pint.UnitRegistry:
    return pint.UnitRegistry()


def normalise(text: str) -> str:
    unit = text.strip().strip("$").strip()
    unit = _TEXT_WRAPPER.sub(r"\1", unit)
    unit = re.sub(r"(?<=[A-Za-z])°", " °", unit)  # "kg°C" -> "kg °C"
    for spelling, pint_name in _SPELLINGS:
        unit = unit.replace(spelling, pint_name)
    unit = _BRACED_POWER.sub(r"^\1", unit)
    return _IMPLIED_PRODUCT.sub("*", unit.strip())


def is_unit(text: str) -> bool:
    """True if ``text`` is a unit Pint understands ("J/(kg °C)", "m/s²", "Ω", "N m")."""
    if text.strip().lower() in NO_UNIT:
        return False
    try:
        _registry().parse_units(normalise(text))
    except (pint.errors.PintError, ValueError, TypeError, AttributeError, KeyError, SyntaxError):
        return False
    return True


def is_no_unit(text: str) -> bool:
    """The example says, explicitly, that its answer has no unit (a ratio, a count, an efficiency)."""
    return text.strip().lower() in NO_UNIT - {""}


_DISPLAY = ((r"\Omega", "Ω"), (r"\mu", "μ"), (r"\cdot", "·"), (r"^{\circ}", "°"), (r"^\circ", "°"))
_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_POWER = re.compile(r"\^\{?(-?\d+)\}?")


def display(text: str) -> str:
    r"""The unit as a textbook prints it, for plain-text display: "$m/s^{2}$" -> "m/s²", "\Omega" -> "Ω"."""
    unit = _TEXT_WRAPPER.sub(r"\1", text.strip().strip("$").strip())
    for latex, symbol in _DISPLAY:
        unit = unit.replace(latex, symbol)
    return _POWER.sub(lambda m: m.group(1).translate(_SUPERSCRIPT), unit).strip()


def dimension(text: str) -> str:
    """The unit's physical dimension, e.g. "[length] / [time] ** 2"; "" when Pint cannot parse it."""
    try:
        return str(_registry().parse_units(normalise(text)).dimensionality)
    except (pint.errors.PintError, ValueError, TypeError, AttributeError, KeyError, SyntaxError):
        return ""


def same_dimension(text: str, reference: str) -> bool:
    """True if both name the same kind of quantity (N and kN: yes; N and A: no)."""
    mine = dimension(text)
    return bool(mine) and mine == dimension(reference)
