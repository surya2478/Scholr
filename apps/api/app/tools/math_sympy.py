"""Deterministic maths tools: safe parsing, equivalence and Cambridge accuracy checks.

Student answers are untrusted input. SymPy's parser evaluates Python, so input is
restricted to a small character whitelist before parsing, and no builtins are exposed.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)


class MathParseError(ValueError):
    """Raised when text cannot be safely parsed as a maths expression."""


_MAX_LEN = 200
_ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z+\-*/^().,=\s]*$")
_WORD = re.compile(r"[A-Za-z]+")
_ATTRIBUTE_ACCESS = re.compile(r"\.\s*[A-Za-z]")
_BIG_EXPONENT = re.compile(r"\^\s*\(?\s*\d{4,}")
_THOUSANDS = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+)(?![\d,])")

_FUNCTIONS: dict[str, object] = {
    "sqrt": sympy.sqrt,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "log": sympy.log,
    "ln": sympy.log,
    "abs": sympy.Abs,
    "pi": sympy.pi,
}

_UNICODE = {
    "\u2212": "-",  # minus sign
    "\u2013": "-",
    "\u00d7": "*",
    "\u00f7": "/",
    "\u00b7": "*",
    "\u03c0": "pi",
    "\u00b2": "^2",
    "\u00b3": "^3",
    "\u00b0": "",
}

_UNITS = re.compile(
    r"\s*(?:cm\^?[23]?|mm\^?[23]?|km\^?[23]?|m\^?[23]?|kg|g|ml|l|litres?|seconds?|s|"
    r"minutes?|hours?|h|degrees?|deg|%)\s*$",
    re.IGNORECASE,
)
_CURRENCY = re.compile(r"^\s*[$\u20b9\u00a3\u20ac]\s*")

_GLOBALS: dict[str, object] = {}
exec("from sympy import *", _GLOBALS)  # noqa: S102 - sympy namespace only
_GLOBALS["__builtins__"] = {}

_TRANSFORMS = (*standard_transformations, implicit_multiplication_application, convert_xor)
_TRANSFORMS_RATIONAL = (*_TRANSFORMS, rationalize)


def _latex_to_plain(text: str) -> str:
    s = text.replace("\\left", "").replace("\\right", "")
    # MathLive (typed answers) wraps units and words, and writes degrees, currency and percent as commands.
    s = re.sub(r"\\(?:mathrm|text|operatorname|mathit|mathbf)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\s*\{\s*\\circ\s*\}|\^\s*\\circ|\\degree", "", s)
    s = s.replace("\\$", "$").replace("\\%", "%")
    frac = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
    root = re.compile(r"\\sqrt\s*\[([^\[\]{}]*)\]\s*\{([^{}]*)\}")
    sqrt = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
    for _ in range(10):
        new = frac.sub(r"((\1)/(\2))", s)
        new = root.sub(r"((\2)^(1/(\1)))", new)
        new = sqrt.sub(r"sqrt(\1)", new)
        if new == s:
            break
        s = new
    s = (
        s.replace("\\times", "*")
        .replace("\\cdot", "*")
        .replace("\\div", "/")
        .replace("\\pi", "pi")
        .replace("\\,", "")
        .replace("\\ ", "")
    )
    return s.replace("{", "(").replace("}", ")")


def strip_units(text: str) -> str:
    """Remove a trailing unit and leading currency symbol from an answer string."""
    s = text.strip()
    for k, v in _UNICODE.items():
        if k in ("\u00b2", "\u00b3"):
            continue
        s = s.replace(k, v)
    s = re.sub(r"(cm|mm|km|m)[\u00b2\u00b3]\s*$", r"\1", s)
    s = _CURRENCY.sub("", s)
    return _UNITS.sub("", s).strip()


def normalize(text: str) -> str:
    s = text.strip()
    for k, v in _UNICODE.items():
        s = s.replace(k, v)
    s = re.sub(r"\u221a\s*(\d+(?:\.\d+)?|[a-z])", r"sqrt(\1)", s)
    s = _latex_to_plain(s)
    s = s.replace("$", "")
    s = _THOUSANDS.sub(lambda m: m.group(1).replace(",", ""), s)
    return s.strip()


def parse_math(text: str, *, rational: bool = False) -> sympy.Expr:
    """Safely parse a maths expression (plain text or simple LaTeX).

    rational=True turns decimal literals into exact rationals before evaluation, so
    "8000*0.75^3" is exactly 3375 rather than a float.
    """
    s = normalize(text)
    if not s:
        raise MathParseError("empty expression")
    if len(s) > _MAX_LEN:
        raise MathParseError("expression too long")
    if not _ALLOWED_CHARS.match(s):
        raise MathParseError("unsupported characters")
    if _ATTRIBUTE_ACCESS.search(s) or "," in s:
        raise MathParseError("unsupported syntax")
    if _BIG_EXPONENT.search(s) or s.count("^") + s.count("**") > 3:
        raise MathParseError("exponent too large")
    for word in _WORD.findall(s):
        if keyword.iskeyword(word) or word.lower() in {"lambda", "exec", "eval"}:
            raise MathParseError("unsupported word")
    if "=" in s:
        lhs, _, rhs = s.partition("=")
        if "=" in rhs:
            raise MathParseError("more than one '='")
        if re.fullmatch(r"\s*[A-Za-z]\s*", lhs):
            s = rhs
        else:
            left, right = parse_math(lhs, rational=rational), parse_math(rhs, rational=rational)
            return sympy.Eq(left, right)  # type: ignore[return-value]
    try:
        expr = parse_expr(
            s,
            local_dict=dict(_FUNCTIONS),
            global_dict=_GLOBALS,
            transformations=_TRANSFORMS_RATIONAL if rational else _TRANSFORMS,
        )
    except Exception as exc:  # noqa: BLE001 - any parser failure is a parse error
        raise MathParseError(f"could not parse: {exc.__class__.__name__}") from exc
    if not isinstance(expr, sympy.Basic):
        raise MathParseError("not a maths expression")
    return expr  # type: ignore[return-value]


_SAMPLE_POINTS = (
    sympy.Rational(3, 7),
    sympy.Rational(11, 13),
    sympy.Rational(-5, 3),
    sympy.Rational(5, 2),
    sympy.Rational(17, 4),
)


def equivalent(a: str | sympy.Expr, b: str | sympy.Expr, *, rel_tol: float = 1e-9) -> bool:
    """True if two expressions are mathematically equal (symbolically or numerically)."""
    ea = parse_math(a) if isinstance(a, str) else a
    eb = parse_math(b) if isinstance(b, str) else b
    if isinstance(ea, sympy.Equality) or isinstance(eb, sympy.Equality):
        return bool(ea == eb)
    diff = sympy.simplify(ea - eb)
    if diff == 0:
        return True
    symbols = sorted(diff.free_symbols, key=lambda s: s.name)
    if not symbols:
        try:
            scale = max(1.0, abs(float(sympy.N(eb))))
            return abs(float(sympy.N(diff))) <= rel_tol * scale
        except (TypeError, ValueError):
            return False
    for i in range(len(_SAMPLE_POINTS)):
        subs = {sym: _SAMPLE_POINTS[(i + j) % len(_SAMPLE_POINTS)] for j, sym in enumerate(symbols)}
        try:
            va = complex(sympy.N(ea.subs(subs)))
            vb = complex(sympy.N(eb.subs(subs)))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(va - vb) > rel_tol * max(1.0, abs(vb)):
            return False
    return True


# ---------------------------------------------------------------------------
# Cambridge numeric accuracy
# ---------------------------------------------------------------------------

Accuracy = Literal["exact", "sf", "dp"]
VerdictStatus = Literal["correct", "insufficient_accuracy", "incorrect", "unparseable"]


@dataclass(frozen=True)
class NumericSpec:
    """How a numeric answer is marked.

    exact: the true value as an expression, e.g. "81.92 + pi*6.4^2/2".
    accuracy: "sf" / "dp" for non-exact answers (Cambridge default 3 sf; angles 1 dp),
              "exact" when only an exactly equal value is acceptable.
    accept_ranges: inclusive ranges copied from a mark scheme ("146.2 to 146.3").
    """

    exact: str
    accuracy: Accuracy = "sf"
    places: int = 3
    accept_ranges: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NumericVerdict:
    status: VerdictStatus
    candidate_value: Decimal | None
    detail: str


_PLAIN_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")


def _to_decimal(expr: sympy.Expr) -> Decimal:
    return Decimal(str(sympy.N(expr, 30)))


def _sig_fig_options(number_text: str) -> range:
    """Possible significant-figure counts for a plain decimal string (trailing zeros are ambiguous)."""
    s = number_text.lstrip("+-")
    if "." in s:
        digits = s.replace(".", "").lstrip("0")
        n = len(digits) if digits else 1
        return range(n, n + 1)
    stripped = s.lstrip("0")
    if not stripped:
        return range(1, 2)
    minimum = len(stripped.rstrip("0")) or 1
    return range(minimum, len(stripped) + 1)


def _decimal_places(number_text: str) -> int:
    s = number_text.lstrip("+-")
    return len(s.split(".", 1)[1]) if "." in s else 0


def round_sig(value: Decimal, figures: int) -> Decimal:
    if value == 0:
        return Decimal(0)
    exponent = value.adjusted() - figures + 1
    return value.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_UP)


def round_dp(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _is_terminating(expr: sympy.Expr) -> bool:
    """True if the exact value (parsed with rational=True) has a terminating decimal expansion."""
    if not expr.is_Rational:
        return False
    q = int(sympy.Rational(expr).q)
    for p in (2, 5):
        while q % p == 0:
            q //= p
    return q == 1


sig_fig_options = _sig_fig_options
decimal_places = _decimal_places


def check_numeric(candidate: str, spec: NumericSpec) -> NumericVerdict:
    """Mark a single numeric answer against Cambridge accuracy conventions."""
    text = strip_units(normalize(candidate))
    try:
        exact_expr = parse_math(spec.exact, rational=True)
        exact = _to_decimal(exact_expr)
    except (MathParseError, InvalidOperation) as exc:
        raise ValueError(f"invalid answer spec: {spec.exact!r}") from exc

    try:
        cand_expr = parse_math(text, rational=True)
        # Plain decimals are read exactly; binary floats would make 0.4 != 2/5.
        cand = Decimal(text) if _PLAIN_NUMBER.match(text) else _to_decimal(cand_expr)
    except (MathParseError, InvalidOperation, TypeError, ValueError):
        return NumericVerdict("unparseable", None, "answer could not be read as a number")

    for lo, hi in spec.accept_ranges:
        if _to_decimal(parse_math(lo)) <= cand <= _to_decimal(parse_math(hi)):
            return NumericVerdict("correct", cand, "within mark-scheme range")

    if not _PLAIN_NUMBER.match(text):
        # Exact forms (fractions, surds, pi) must be exactly equal.
        if equivalent(cand_expr, exact_expr):
            return NumericVerdict("correct", cand, "exact form")
        return NumericVerdict("incorrect", cand, "not equal to the exact value")

    if cand == exact:
        return NumericVerdict("correct", cand, "exact value")

    if spec.accuracy == "exact" or _is_terminating(exact_expr) and exact == round_sig(exact, 8):
        options = _sig_fig_options(text)
        if any(round_sig(exact, n) == cand for n in options):
            return NumericVerdict("insufficient_accuracy", cand, "exact answer was required")
        return NumericVerdict("incorrect", cand, "not equal to the exact value")

    if spec.accuracy == "sf":
        options = _sig_fig_options(text)
        if round_sig(cand, spec.places) == round_sig(exact, spec.places) and max(options) >= spec.places:
            return NumericVerdict("correct", cand, f"correct to {spec.places} sf")
        if any(n < spec.places and round_sig(exact, n) == cand for n in options):
            return NumericVerdict("insufficient_accuracy", cand, f"needs {spec.places} sf")
        return NumericVerdict("incorrect", cand, "value is wrong")

    places = _decimal_places(text)
    if places >= spec.places and round_dp(cand, spec.places) == round_dp(exact, spec.places):
        return NumericVerdict("correct", cand, f"correct to {spec.places} dp")
    if places < spec.places and round_dp(exact, places) == cand:
        return NumericVerdict("insufficient_accuracy", cand, f"needs {spec.places} dp")
    return NumericVerdict("incorrect", cand, "value is wrong")
