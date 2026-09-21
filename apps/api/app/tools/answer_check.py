"""Deterministic final-answer checks against a question item's ``answer_spec`` (Cambridge conventions).

answer_spec, as written by the question bank: {"type", "answer", "exact", "accuracy", "accept_ranges"}.
The verdict is authoritative for the final answer only; method marks stay with the evaluator.
"not_checked" means the tool cannot decide (e.g. an answer whose form matters), never "probably right".
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import sympy

from app.tools.math_sympy import (
    MathParseError,
    NumericSpec,
    check_numeric,
    decimal_places,
    equivalent,
    normalize,
    parse_math,
    round_dp,
    round_sig,
    sig_fig_options,
    strip_units,
)

ToolStatus = Literal["correct", "insufficient_accuracy", "incorrect", "unparseable", "not_checked"]
_SEVERITY = {"unparseable": 0, "incorrect": 1, "not_checked": 2, "insufficient_accuracy": 3, "correct": 4}

_ACCURACY = {"sf3": ("sf", 3), "dp1_angle": ("dp", 1), "exact": ("exact", 3)}
_PLAIN = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")
_NAMED = re.compile(r"^\s*([A-Za-z])\s*=\s*(.+)$")
_RANGE = re.compile(r"^(\S+)\s+to\s+(\S+)$", re.IGNORECASE)
_MARK_CODES = re.compile(r"\b(?:SC|[MAB])\d\b")
_NOTATION = re.compile(r"\b(?:oe|cao|isw|nfww|www|soi|dep|ft|final answer|seen|accept|condone)\b\.?", re.IGNORECASE)
# Command words where the form of the answer is assessed, so equivalence alone cannot award the mark.
FORM_COMMANDS = frozenset({"factorise", "factorize", "simplify", "expand", "rearrange", "express", "write", "make"})


@dataclass(frozen=True)
class ToolVerdict:
    status: ToolStatus
    method: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _clean(scheme_text: str) -> str:
    text = _NOTATION.sub(" ", _MARK_CODES.sub(" ", scheme_text))
    return re.sub(r"\s+", " ", text).strip(" .;")


def _alternatives(scheme_answer: str) -> list[str]:
    return [a for a in (_clean(p) for p in re.split(r"\s+or\s+|;", scheme_answer, flags=re.IGNORECASE)) if a]


def _strip_name(text: str) -> str:
    normal = normalize(text)
    match = _NAMED.match(normal)
    return strip_units(match.group(2) if match else normal)


def _decimal_of(text: str) -> tuple[Decimal, str] | None:
    """(value, cleaned text) for a number or a closed-form numeric expression; None if not numeric."""
    cleaned = _strip_name(text)
    if not cleaned:
        return None
    if _PLAIN.match(cleaned):
        return Decimal(cleaned), cleaned
    try:
        value = Decimal(str(sympy.N(parse_math(cleaned, rational=True), 30)))
    except (MathParseError, InvalidOperation, TypeError, ValueError):
        return None
    return (value, cleaned) if value.is_finite() else None


def _sig_figs(text: str) -> list[int]:
    return list(sig_fig_options(text)) if _PLAIN.match(text) else [30]


def compare_to_printed(candidate: str, printed: str, *, accuracy: str) -> ToolStatus:
    """Compare against a rounded answer printed in a mark scheme (used when no exact value is known)."""
    cand, ref = _decimal_of(candidate), _decimal_of(printed)
    if cand is None:
        return "unparseable"
    if ref is None:
        return "not_checked"
    (cv, ct), (rv, rt) = cand, ref
    if cv == rv:
        return "correct"
    if accuracy == "dp1_angle":
        ref_dp = decimal_places(rt) if _PLAIN.match(rt) else 1
        cand_dp = decimal_places(ct) if _PLAIN.match(ct) else 30
        if cand_dp >= ref_dp and round_dp(cv, ref_dp) == rv:
            return "correct"
        if cand_dp < ref_dp and round_dp(rv, cand_dp) == cv:
            return "insufficient_accuracy"
        return "incorrect"
    cand_sf = max(_sig_figs(ct))
    ref_options = _sig_figs(rt)
    if accuracy != "exact" and any(cand_sf >= n and round_sig(cv, n) == rv for n in ref_options):
        return "correct"
    if cand_sf < max(ref_options) and round_sig(rv, cand_sf) == cv:
        return "insufficient_accuracy"
    return "incorrect"


def _check_numeric_item(final_answer: str, spec: dict[str, Any]) -> ToolVerdict:
    cand = _decimal_of(final_answer)
    if cand is None:
        return ToolVerdict("unparseable", "numeric", "the final answer could not be read as a number")
    accuracy = str(spec.get("accuracy") or "sf3")
    ranges = [tuple(r) for r in spec.get("accept_ranges") or [] if len(r) == 2]
    printed: list[str] = []
    for alternative in _alternatives(str(spec.get("answer") or "")):
        match = _RANGE.match(alternative)
        if match:
            ranges.append((match.group(1), match.group(2)))
        else:
            printed.append(alternative)

    for lo, hi in ranges:
        lo_v, hi_v = _decimal_of(str(lo)), _decimal_of(str(hi))
        if lo_v and hi_v and lo_v[0] <= cand[0] <= hi_v[0]:
            return ToolVerdict("correct", "mark_scheme_range", "within the mark-scheme range")

    if spec.get("exact"):
        kind, places = _ACCURACY.get(accuracy, ("sf", 3))
        try:
            verdict = check_numeric(cand[1], NumericSpec(exact=str(spec["exact"]), accuracy=kind, places=places))  # type: ignore[arg-type]
            return ToolVerdict(verdict.status, "sympy_exact", verdict.detail)
        except ValueError:
            pass  # unusable exact value: fall back to the printed answer

    statuses = [s for s in (compare_to_printed(cand[1], p, accuracy=accuracy) for p in printed) if s != "not_checked"]
    if not statuses:
        return ToolVerdict("not_checked", "printed_answer", "the mark-scheme answer is not a single number")
    return ToolVerdict(
        max(statuses, key=_SEVERITY.__getitem__), "printed_answer", f"compared with {len(statuses)} printed answer(s)"
    )


def _check_expression(final_answer: str, spec: dict[str, Any], command_word: str | None) -> ToolVerdict:
    try:
        cand = parse_math(final_answer)
    except MathParseError:
        return ToolVerdict("unparseable", "expression", "the final answer could not be read as an expression")
    compared = False
    for alternative in _alternatives(str(spec.get("answer") or "")):
        try:
            same = equivalent(cand, parse_math(alternative))
        except (MathParseError, TypeError, ValueError):
            continue
        compared = True
        if same:
            first_word = (command_word or "").strip().split(" ")[0].lower()
            if first_word in FORM_COMMANDS or spec.get("accuracy") == "exact":
                return ToolVerdict("not_checked", "sympy_equivalence", "equivalent, but the required form is assessed")
            return ToolVerdict("correct", "sympy_equivalence", "equivalent to the mark-scheme answer")
    if not compared:
        return ToolVerdict("not_checked", "sympy_equivalence", "the mark-scheme answer is not machine-readable")
    return ToolVerdict("incorrect", "sympy_equivalence", "not equivalent to the mark-scheme answer")


def _split_values(text: str) -> list[tuple[str | None, str]]:
    body = normalize(text).strip().strip("()[]")
    values: list[tuple[str | None, str]] = []
    for part in re.split(r"\s*(?:,|;|\band\b)\s*", body):
        if not part.strip():
            continue
        match = _NAMED.match(part)
        values.append((match.group(1).lower(), match.group(2).strip()) if match else (None, part.strip()))
    return values


def _value_status(candidate: str, reference: str, accuracy: str) -> ToolStatus:
    status = compare_to_printed(candidate, reference, accuracy=accuracy)
    if status == "not_checked":
        try:
            return "correct" if equivalent(parse_math(candidate), parse_math(reference)) else "incorrect"
        except (MathParseError, TypeError, ValueError):
            return "not_checked"
    return status


def _check_values(final_answer: str, spec: dict[str, Any], *, ordered: bool) -> ToolVerdict:
    method = "ordered_values" if ordered else "set_of_values"
    alternatives = _alternatives(str(spec.get("answer") or ""))
    if not alternatives:
        return ToolVerdict("not_checked", method, "no mark-scheme answer")
    cand, ref = _split_values(final_answer), _split_values(alternatives[0])
    accuracy = str(spec.get("accuracy") or "sf3")
    if len(cand) != len(ref):
        return ToolVerdict("incorrect", method, f"expected {len(ref)} value(s), got {len(cand)}")

    statuses: list[ToolStatus] = []
    if all(name for name, _ in cand) and all(name for name, _ in ref):
        given = dict(cand)
        for name, value in ref:
            statuses.append(_value_status(given[name], value, accuracy) if name in given else "incorrect")
    elif ordered:
        statuses = [_value_status(c, r, accuracy) for (_, c), (_, r) in zip(cand, ref, strict=True)]
    else:
        remaining = [c for _, c in cand]
        for _, r in ref:
            scored = sorted(((_value_status(c, r, accuracy), c) for c in remaining), key=lambda x: -_SEVERITY[x[0]])
            best_status, best_value = scored[0]
            statuses.append(best_status)
            remaining.remove(best_value)
    return ToolVerdict(min(statuses, key=_SEVERITY.__getitem__), method, f"{len(statuses)} value(s) compared")


def check_final_answer(
    final_answer: str | None, answer_spec: dict[str, Any], *, command_word: str | None = None
) -> ToolVerdict:
    kind = str(answer_spec.get("type") or "")
    if kind not in ("numeric", "expression", "coordinates", "set_of_values"):
        return ToolVerdict("not_checked", kind or "unknown", "this answer type is marked by the evaluator")
    if not final_answer or not final_answer.strip():
        return ToolVerdict("unparseable", kind, "no final answer was given")
    if kind == "numeric":
        return _check_numeric_item(final_answer, answer_spec)
    if kind == "expression":
        return _check_expression(final_answer, answer_spec, command_word)
    return _check_values(final_answer, answer_spec, ordered=kind == "coordinates")
