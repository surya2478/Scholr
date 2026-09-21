"""The exam level of a topic page (docs/STUDENT-APP.md AC-U16).

A lesson explains the idea; this shows her what the exam does with it, from material that is already checked:
the past-paper questions in the bank, their official mark schemes and what the examiners wrote about them.

- ``how_examined`` counts, from the bank, how often and in what shape the topic has been asked. No model.
- ``pick_worked`` chooses one past-paper question to solve in front of her, by fixed rules.
- ``guard_walkthrough`` checks a model's step-by-step solution of that question before it is stored: its final
  answer must be the mark scheme's (``tools.answer_check``, the same check that marks her answers), and every mark
  it names (M1, A1, B1…) must be one the mark scheme awards. A walkthrough that fails is not shown at all.

A walkthrough is only written for subjects whose worked examples are checked by SymPy (the subject config says
which). A Sociology answer cannot be checked this way, and Scholr does not write her exam answers (AC-R5).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import sympy
from pydantic import BaseModel, ConfigDict, Field

from app.llm.text_repair import repair_json_escapes
from app.tools import answer_check
from app.tools.math_sympy import MathParseError, parse_math

WALKTHROUGH_VERSION = "exam_walkthrough_guard_v3"
MIN_STEPS = 2
MAX_STEPS = 8
MAX_STEP_WORDS = 90
COMMAND_WORDS = 3
_REF = re.compile(r"^(?P<syllabus>\d{4})/(?P<paper>\d)(?P<variant>\d)/(?P<session>[A-Z]{2})(?P<year>\d{2})/")
_MARK = re.compile(r"^(?:SC|[MAB])\d$")
_MARKS_IN_SCHEME = re.compile(r"\b((?:SC|[MAB])\d)\b")
_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")
# A question that only makes sense with an earlier part or a figure in front of her is a poor one to solve on a
# phone: "Use your graph", "on the grid", "the diagram shows".
_NEEDS_EARLIER_PART = re.compile(r"\b(?:your graph|your answer to|the grid|your table|part \()", re.IGNORECASE)
# The exception: "By drawing a suitable straight line, solve ..." on a curve whose equation the question states.
# The method is the whole point of these Extended questions, and it can be followed without the picture.
_BY_DRAWING = re.compile(r"\bby drawing a suitable (?:straight )?line", re.IGNORECASE)
_CURVE_GIVEN = re.compile(r"\by\s*=")


@dataclass(frozen=True)
class ExamItem:
    """What this module needs to know about one bank item (read through the assessment service)."""

    id: str
    source_ref: str | None
    origin: str
    stem: str
    context: str | None
    marks: int
    command_word: str | None
    has_diagram: bool
    answer_spec: dict
    mark_scheme: dict


class Brief(Protocol):
    """Enough of a bank item to count it: an ``ExamItem`` or the assessment service's ``ItemBrief``."""

    @property
    def origin(self) -> str: ...
    @property
    def source_ref(self) -> str | None: ...
    @property
    def marks(self) -> int: ...
    @property
    def command_word(self) -> str | None: ...


@dataclass(frozen=True)
class HowExamined:
    asked: int
    marks_min: int
    marks_max: int
    papers: list[str]
    years: list[str]
    command_words: list[str]


def _paper(source_ref: str | None) -> tuple[str, str] | None:
    """("Paper 2", "2024") for "0580/21/MJ24/Q18"; None for anything that is not a past paper."""
    match = _REF.match(source_ref or "")
    if match is None:
        return None
    return f"Paper {match['paper']}", f"20{match['year']}"


def how_examined(items: Sequence[Brief]) -> HowExamined | None:
    """How the papers in the bank have asked about this topic. Nothing is said when there are no past papers."""
    past = [i for i in items if i.origin == "past_paper" and _paper(i.source_ref)]
    if not past:
        return None
    papers = sorted({_paper(i.source_ref)[0] for i in past})  # type: ignore[index]
    years = sorted({_paper(i.source_ref)[1] for i in past})  # type: ignore[index]
    commands = Counter((i.command_word or "").strip().lower() for i in past if (i.command_word or "").strip())
    return HowExamined(
        asked=len(past),
        marks_min=min(i.marks for i in past),
        marks_max=max(i.marks for i in past),
        papers=papers,
        years=years,
        command_words=[word for word, _ in commands.most_common(COMMAND_WORDS)],
    )


_LABEL = re.compile(r"\[[^\]]*=\s*\]")  # "[x =]", "[A =]"
_NOTATION = re.compile(r"\b(?:oe|cao|isw|nfww|www|soi|dep|ft|final answer|seen)\b\.?", re.IGNORECASE)
_RANGE = re.compile(r"([-−]?\d+(?:\.\d+)?)\s+to\s+[-−]?\d+(?:\.\d+)?")
_TRAILING_AND = re.compile(r"\s+and\s*$", re.IGNORECASE)
_WORDS = re.compile(r"\b(?!(?:sqrt|sin|cos|tan|and)\b)[A-Za-z]{3,}\b")


def _answer_line(line: str, *, every_alternative: bool = False) -> str:
    """One line of a printed scheme answer as a student would write it: "[x =] 1.25 or 1.250… oe" -> "1.25";
    a range "−3.95 to −3.75" -> its first end (the range is inclusive). With ``every_alternative`` the parts joined
    by "or" are kept as a list — some schemes print two roots as "x = −0.5 to −0.55 or x = 0.85 to 0.9"."""
    line = _NOTATION.sub(" ", _LABEL.sub(" ", line))
    parts = re.split(r"\s+or\s+", line.strip(), flags=re.IGNORECASE)
    parts = parts if every_alternative else parts[:1]
    cleaned = [" ".join(_RANGE.sub(lambda m: m.group(1), p).split()) for p in parts]
    return ", ".join(x for x in (_TRAILING_AND.sub("", p).strip(" ;,…") for p in cleaned) if x)


def _is_value(line: str) -> bool:
    """A line that states a value rather than describing working ("ruled line y = 2x + 1", "leading to ...")."""
    return not _WORDS.search(line)


def official_answers(answer: str) -> list[str]:
    """Ways to write the scheme's answer that a student might give: its first line, its value lines together, or
    its last one to three value lines (schemes often print working above the answer), each with and without the
    alternatives the scheme joins with "or"."""
    out: list[str] = []
    for every in (False, True):
        lines = [x for x in (_answer_line(line, every_alternative=every) for line in answer.splitlines()) if x]
        if not lines:
            continue
        values = [x for x in lines if _is_value(x)] or lines
        out += [lines[0], ", ".join(values), *(", ".join(values[-k:]) for k in (1, 2, 3) if k <= len(values))]
    return list(dict.fromkeys(out))


def checkable(item: ExamItem) -> bool:
    """Whether code can tell a right final answer from a wrong one for this item: some way of writing the scheme's
    own answer must pass the check that marks hers (proof the checker can read this answer), and the scheme must
    name its marks. The walkthrough is then held to the same check, so this only decides which items to try."""
    if not scheme_marks(item.mark_scheme):
        return False
    return any(
        answer_check.check_final_answer(candidate, item.answer_spec, command_word=item.command_word).status == "correct"
        for candidate in official_answers(str(item.answer_spec.get("answer") or ""))
    )


def stands_alone(item: ExamItem) -> bool:
    return not item.has_diagram and not _NEEDS_EARLIER_PART.search(f"{item.context or ''} {item.stem}")


def graph_by_drawing(item: ExamItem) -> bool:
    return bool(_BY_DRAWING.search(item.stem) and _CURVE_GIVEN.search(item.context or ""))


def pick_worked(items: Sequence[ExamItem]) -> ExamItem | None:
    """The past-paper question to solve in front of her: one whose answer code can check, that stands on its own
    (no figure, no earlier part), worth the most marks — an exam-level question, not a warm-up. Ties go to the
    most recent paper. Returns None when no item qualifies; the page then shows no worked question."""

    def recency(item: ExamItem) -> tuple[int, int]:
        match = _REF.match(item.source_ref or "")
        if match is None:
            return (0, 0)
        return (int(match["year"]), {"FM": 1, "MJ": 2, "ON": 3}.get(match["session"], 0))

    candidates = [
        i
        for i in items
        if i.origin == "past_paper" and (stands_alone(i) or graph_by_drawing(i)) and i.marks >= 2 and checkable(i)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda i: (i.marks, recency(i), i.source_ref or ""))


def scheme_marks(mark_scheme: dict) -> set[str]:
    """The mark codes the official scheme can award for this item: {"M1", "A1", "B1", "SC1"}."""
    return set(_MARKS_IN_SCHEME.findall(str(mark_scheme.get("text") or "")))


def marks_allowed(item: ExamItem) -> str:
    return ", ".join(sorted(scheme_marks(item.mark_scheme))) or "none"


def scheme_text(item: ExamItem) -> str:
    """The mark scheme as the walkthrough writer sees it: the answer line and the guidance lines."""
    answer = str(item.answer_spec.get("answer") or "").strip()
    guidance = str(item.mark_scheme.get("text") or "").strip()
    return "\n".join(x for x in (f"Answer: {answer}" if answer else "", guidance) if x)


class WalkthroughStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    # The mark this step earns in the official scheme ("M1", "A1", "B1"), or "" for a step that earns none.
    mark: str = ""


class WalkthroughDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    steps: list[WalkthroughStep] = Field(default_factory=list)
    final_answer: str
    tip: str = ""


@dataclass
class WalkthroughReport:
    kept: bool = False
    reason: str = ""
    steps: int = 0
    marks_named: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _marks_value(code: str) -> int:
    return int(code[-1])


_NAME = re.compile(r"^\s*\[?\s*[A-Za-z]\s*=\s*\]?\s*")
_VALUE_SEPARATOR = re.compile(r"\s*(?:,|;|\band\b)\s*")


def answer_status(final: str, item: ExamItem) -> str:
    """Whether a final answer is the scheme's, by the check that marks hers. A scheme that prints several values on
    separate lines ("x = −1.7 to −1.4" / "x = 2" / "x = 4.4 to 4.7") is matched value by value, each against its
    own line only, so one value cannot borrow another's range."""
    spec, command = item.answer_spec, item.command_word
    status = answer_check.check_final_answer(final, spec, command_word=command).status
    if status == "correct" or spec.get("type") not in ("numeric", "set_of_values"):
        return status
    lines = [
        _NAME.sub("", line).strip()
        for line in str(spec.get("answer") or "").splitlines()
        if line.strip() and _is_value(_answer_line(line))
    ]
    values = [_NAME.sub("", v) for v in _VALUE_SEPARATOR.split(final) if v.strip()]
    if len(lines) < 2 or len(values) != len(lines):
        return status
    remaining = list(lines)
    for value in values:
        match = next(
            (
                line
                for line in remaining
                if answer_check.check_final_answer(
                    value, {**spec, "type": "numeric", "answer": line, "accept_ranges": []}, command_word=command
                ).status
                == "correct"
            ),
            None,
        )
        if match is None:
            return status
        remaining.remove(match)
    return "correct"


_MATH = re.compile(r"\$([^$]+)\$")
_Y_IS = re.compile(r"\by\s*=\s*(.+)")
_EQUATION = re.compile(r"equation\s+\$?([^$]+?=[^$]+?)\$?\s*(?:for\b|\.?\s*$)", re.IGNORECASE)
_X = sympy.Symbol("x")
_SENTENCE_WORD = re.compile(r"(?<![A-Za-z])(?!(?:sqrt|sin|cos|tan)(?![A-Za-z]))[A-Za-z]{2,}")


def _expr(text: str) -> sympy.Expr | None:
    try:
        return parse_math(text.strip().rstrip(".,;"))
    except (MathParseError, TypeError, ValueError):
        return None


def _curve_and_equation(item: ExamItem) -> tuple[sympy.Expr, sympy.Expr] | None:
    """(f, g) for "the graph of y = f(x)" and "solve the equation L = R" (g = L - R)."""
    context = _MATH.sub(lambda m: m.group(1), item.context or "")
    curve = _Y_IS.search(context)
    equation = _EQUATION.search(item.stem)
    if curve is None or equation is None:
        return None
    # The curve's expression ends where the sentence goes on in words: "... for −3 ≤ x ≤ 1.5", "... is drawn."
    words = _SENTENCE_WORD.search(curve.group(1))
    f = _expr((curve.group(1)[: words.start()] if words else curve.group(1)).strip().rstrip("."))
    left, _, right = equation.group(1).partition("=")
    g_left, g_right = _expr(left), _expr(right)
    if f is None or g_left is None or g_right is None:
        return None
    return f, g_left - g_right


_NUMBER = re.compile(r"^[+-]?\d+(?:\.(\d+))?$")
_APPROX = re.compile(r"\\approx|≈")


def _tolerance(printed: str) -> float:
    """How far a printed value may be from the exact one: half a unit in its last decimal place ("146.3" may stand
    for 146.2566…), and practically nothing for a whole number or an expression."""
    match = _NUMBER.match(printed.strip())
    if match and match.group(1):
        return 0.5 * 10 ** -len(match.group(1)) + 1e-12
    return 1e-9


def arithmetic_holds(steps: Sequence[str]) -> bool:
    """Every chain of numeric equalities written in the steps' maths is true: "$54 = 2 × 27 = 2 × 3 × 9$" is
    recomputed by SymPy. Parts with a letter in them, or that cannot be read, are not judged here."""
    for text in steps:
        for segment in _MATH.findall(text):
            if _APPROX.search(segment) or "=" not in segment:
                continue
            parts = [p.strip() for p in segment.split("=")]
            values: list[tuple[float, str]] = []
            for part in parts:
                expr = _expr(part) if part else None
                if expr is None or expr.free_symbols:
                    values = []
                    break
                try:
                    values.append((float(sympy.N(expr, 30)), part))
                except (TypeError, ValueError):
                    values = []
                    break
            for (a, pa), (b, pb) in zip(values, values[1:], strict=False):
                if abs(a - b) > max(_tolerance(pa), _tolerance(pb)):
                    return False
    return True


def lines_named(steps: Sequence[str]) -> list[sympy.Expr]:
    """Every "y = ..." written in the steps' maths, as expressions in x."""
    out = []
    for text in steps:
        for segment in _MATH.findall(text):
            for match in _Y_IS.finditer(segment):
                expr = _expr(match.group(1))
                if expr is not None:
                    out.append(expr)
    return out


def line_to_draw(item: ExamItem) -> str | None:
    """The straight line whose crossings with the curve solve the equation, computed rather than asked for:
    y = f − k·g, with k chosen to cancel every power of x above the first. None when no such k exists or the
    question cannot be read. (Flash-Lite got the sign of this rearrangement wrong in three runs out of three.)"""
    given = _curve_and_equation(item)
    if given is None:
        return None
    f, g = (sympy.Poly(sympy.expand(e), _X) for e in given)
    if g.degree() < 2 or f.degree() != g.degree():
        return None
    line = sympy.expand(f.as_expr() - (f.LC() / g.LC()) * g.as_expr())
    if sympy.degree(line, _X) > 1:
        return None
    return f"y = {sympy.latex(line, order='rev-lex')}"


def right_line(steps: Sequence[str], item: ExamItem) -> bool:
    """For "by drawing a suitable straight line, solve g = 0" on the curve y = f: every straight line the steps name
    must be one whose crossings with the curve solve the equation — f − line is a non-zero constant times g
    (SymPy) — and there must be one. "Draw y = x − 10" where the scheme's line is y = 10 − x fails."""
    given = _curve_and_equation(item)
    if given is None:
        return False
    f, g = given
    named = [e for e in lines_named(steps) if e.free_symbols <= {_X} and sympy.simplify(e - f) != 0]
    if not named:
        return False
    for line in named:
        if sympy.degree(sympy.expand(line), _X) > 1:
            return False
        ratio = sympy.simplify((f - line) / g)
        if ratio.free_symbols or ratio == 0:
            return False
    return True


def guard_walkthrough(draft: WalkthroughDraft, item: ExamItem) -> tuple[dict | None, WalkthroughReport]:
    """Keep a walkthrough only if it reaches the mark scheme's answer and names only marks the scheme awards."""
    report = WalkthroughReport()
    fix = repair_json_escapes
    steps = [(fix(s.text).strip(), s.mark.strip().upper()) for s in draft.steps if s.text.strip()]
    final = fix(draft.final_answer).strip()
    tip = fix(draft.tip).strip()
    report.steps = len(steps)

    def reject(reason: str) -> tuple[None, WalkthroughReport]:
        report.reason = reason
        return None, report

    if not MIN_STEPS <= len(steps) <= MAX_STEPS:
        return reject("step_count")
    # A line break inside a step is a LaTeX command JSON decoding broke ("\neq" read as newline + "eq").
    if any(_CONTROL.search(t) or "\n" in t for t in (final, tip, *(text for text, _ in steps))):
        return reject("garbled")
    if any(len(text.split()) > MAX_STEP_WORDS for text, _ in steps):
        return reject("step_too_long")
    status = answer_status(final, item)
    if status != "correct":
        return reject(f"answer_{status}")
    if not arithmetic_holds([text for text, _ in steps]):
        return reject("arithmetic")
    if graph_by_drawing(item) and not right_line([text for text, _ in steps], item):
        return reject("wrong_line")
    named = [mark for _, mark in steps if mark]
    report.marks_named = named
    allowed = scheme_marks(item.mark_scheme)
    if not named:
        return reject("no_marks")
    if any(not _MARK.match(mark) or mark not in allowed for mark in named):
        return reject("mark_not_in_scheme")
    if sum(_marks_value(mark) for mark in named if not mark.startswith("SC")) > item.marks:
        return reject("too_many_marks")
    report.kept = True
    return {
        "item_id": item.id,
        "source_ref": item.source_ref,
        "steps": [{"text": text, "mark": mark} for text, mark in steps],
        "final_answer": final,
        "tip": tip,
        "checked": "mark_scheme",
        "guard_version": WALKTHROUGH_VERSION,
        # Code checks the answer, the marks, the arithmetic and (for graph questions) the line; it cannot check
        # reasoning written in words. So, like a diagram, it reaches her only once a person has read it.
        "approved": False,
    }, report
