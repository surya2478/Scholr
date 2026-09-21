"""Topic lessons: the shape a model must return, and the guard that decides what of it may be stored.

A lesson is Scholr's own explanation of one objective, written from excerpts of the student's course material
(docs/STUDENT-APP.md, AC-U3–U5). Everything here is deterministic; the model call lives in the service.

What the guard enforces:
- every section and key term cites at least one excerpt it was given; a section citing nothing is dropped;
- nothing copies its sources (a run of ``COPY_RUN`` words shared with the cited excerpts drops it);
- where the subject requires citations for named studies, a name the cited excerpts do not contain — "Oakley
  (1974)" or any capitalised word inside a sentence — drops the section;
- a worked example in a subject that asks for SymPy checking is kept only if SymPy, evaluating the example's
  own ``answer_expression``, agrees with the answer it prints.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import sympy
from pydantic import BaseModel, ConfigDict, Field

from app.llm.text_repair import repair_json_escapes
from app.modules.learn import diagrams
from app.tools import text_overlap, units
from app.tools.math_sympy import MathParseError, NumericSpec, check_numeric, equivalent, parse_math

# v3: repair LaTeX damaged by JSON; v4: list answers value by value; v5: drop parts still garbled;
# v6: units checked with Pint where the subject's answers carry units (not repeated if the answer already names it)
GUARD_VERSION = "lesson_guard_v7"
COPY_RUN = 12
# A worked example may not reuse a past-paper question: she is meant to try those herself (lesson v4).
PAST_PAPER_RUN = 8
LEVELS = ("basic", "standard", "exam")
# Durable content is held to a higher bar than a chat turn: a lesson is written only from well-matched material.
GROUNDED_STATES = frozenset({"HIGH", "MEDIUM"})
MIN_SECTIONS = 1
_CAPITALISED = re.compile(r"\b[A-Z][a-zA-Z'-]{3,}\b")
_SENTENCE_START = ".!?:;\"'“‘*-•"
_NAMED_WORK = re.compile(
    r"\b([A-Z][a-zA-Z'-]+)(?:\s+(?:and|&)\s+[A-Z][a-zA-Z'-]+)?(?:\s+et al\.?)?\s*\((1[89]\d\d|20\d\d)\)"
)


class DraftSection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    heading: str
    body: str
    sources: list[int] = Field(default_factory=list)


class DraftTerm(BaseModel):
    model_config = ConfigDict(extra="ignore")
    term: str
    meaning: str
    sources: list[int] = Field(default_factory=list)


class DraftExample(BaseModel):
    model_config = ConfigDict(extra="ignore")
    problem: str
    steps: list[str] = Field(default_factory=list)
    final_answer: str
    # The answer written as one SymPy-readable expression from the problem's own numbers, e.g. "sqrt(5^2+12^2)".
    answer_expression: str = ""
    # The answer's unit, kept apart from the value so SymPy checks the number and Pint checks the unit.
    unit: str = ""
    sources: list[int] = Field(default_factory=list)
    level: str = ""  # lesson v4: "basic", "standard" or "exam"


class DiagramDraft(BaseModel):
    """One diagram a model proposes for a lesson: a kind from the subject's vocabulary, and its numbers."""

    model_config = ConfigDict(extra="ignore")
    kind: str
    caption: str = ""
    data: dict = Field(default_factory=dict)
    sources: list[int] = Field(default_factory=list)


class DiagramDrafts(BaseModel):
    model_config = ConfigDict(extra="ignore")
    diagrams: list[DiagramDraft] = Field(default_factory=list)


class LessonDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    sections: list[DraftSection] = Field(default_factory=list)
    key_terms: list[DraftTerm] = Field(default_factory=list)
    worked_examples: list[DraftExample] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Excerpt:
    """One retrieved chunk as the guard sees it (numbered from 1 in the prompt)."""

    chunk_id: str
    source_title: str
    page: int | None
    text: str


@dataclass
class GuardReport:
    kept_sections: int = 0
    dropped_uncited: int = 0
    dropped_copied: int = 0
    dropped_unsupported_name: int = 0
    kept_examples: int = 0
    dropped_examples_unchecked: int = 0
    dropped_examples_wrong: int = 0
    dropped_terms: int = 0
    dropped_garbled: int = 0
    dropped_examples_unit: int = 0
    dropped_examples_past_paper: int = 0
    dropped_past_paper: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass
class GuardedLesson:
    summary: str
    sections: list[dict] = field(default_factory=list)
    key_terms: list[dict] = field(default_factory=list)
    worked_examples: list[dict] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    report: GuardReport = field(default_factory=GuardReport)

    @property
    def usable(self) -> bool:
        return len(self.sections) >= MIN_SECTIONS

    def content(self) -> dict:
        return {
            "summary": self.summary,
            "sections": self.sections,
            "key_terms": self.key_terms,
            "worked_examples": self.worked_examples,
            "pitfalls": self.pitfalls,
        }


def _cited(numbers: Sequence[int], excerpts: Sequence[Excerpt]) -> list[int]:
    return [n for n in dict.fromkeys(numbers) if 0 < n <= len(excerpts)]


def _source_refs(numbers: Sequence[int], excerpts: Sequence[Excerpt]) -> list[dict]:
    return [
        {"chunk_id": excerpts[n - 1].chunk_id, "title": excerpts[n - 1].source_title, "page": excerpts[n - 1].page}
        for n in numbers
    ]


def _fold(text: str) -> str:
    """Lower case without accents, so "Goran" in a lesson matches "Göran" in the book."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def unsupported_names(text: str, sources: str) -> list[str]:
    """Names the cited excerpts never mention: "Oakley (1974)", and any capitalised word inside a sentence
    ("as Parsons argued") — a sociologist, study, place or organisation. A plural ("Marxists") matches its
    singular. Checked against the whole of every excerpt the passage cites."""
    folded = _fold(sources)
    found = [m.group(1) for m in _NAMED_WORK.finditer(text) if _fold(m.group(1)) not in folded]
    for m in _CAPITALISED.finditer(text):
        before = text[: m.start()].rstrip()
        if not before or before[-1] in _SENTENCE_START:
            continue
        word = _fold(m.group(0))
        if word not in folded and not (word.endswith("s") and word[:-1] in folded):
            found.append(m.group(0))
    return found


_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")


_SET_CALL = re.compile(r"^\s*(?:set|FiniteSet)\(\s*\[?(.*?)\]?\s*\)\s*$")
_SET_BRACES = re.compile(r"^\s*\\?\{(.*)\\?\}\s*$")
_LIST_SEPARATOR = re.compile(r",|;|\s+and\s+")
_MATH_SEGMENT = re.compile(r"\$([^$]+)\$")
_LABEL = re.compile(r"^\s*[A-Za-z][A-Za-z ]*?\s*=\s*")
_TRAILING_WORDS = re.compile(r"(?:\s+[A-Za-z]+\.?)+\s*$")
_LEAD_IN = re.compile(r"^.*\b(?:is|are|equals|gives)\s+", re.IGNORECASE)


def _values(text: str) -> list[str]:
    """A printed answer as its values: "1, 8, 27" -> three; "12 m and 42 m" -> two; "{1, 3, 5}" or
    "set([1, 3, 5])" -> three; "$16,240" -> one (a thousands separator is not a list)."""
    text = _THOUSANDS.sub("", text.strip())
    for wrapper in (_SET_CALL, _SET_BRACES):
        if m := wrapper.match(text):
            text = m.group(1)
    return [v.strip() for v in _LIST_SEPARATOR.split(text) if v.strip()]


def _readings(answer: str) -> list[str]:
    """Ways to read one printed value: as written, the maths inside $...$, without a label ("LCM = 360"), without
    trailing units ("15 tiles", "4w + 10 cm") and after a lead-in ("The perimeter is 4w + 10"). Only words are
    removed — the value that remains must still match what SymPy computes."""
    readings = [answer]
    segments = _MATH_SEGMENT.findall(answer)
    if len(segments) == 1:
        readings.append(segments[0])
    for text in list(readings):
        for pattern in (_LABEL, _LEAD_IN):
            readings.append(pattern.sub("", text))
    readings.extend(_TRAILING_WORDS.sub("", text) for text in list(readings))
    return [r.strip() for r in dict.fromkeys(readings) if r.strip()]


def _answer_words(answer: str) -> set[str]:
    """The whitespace-separated tokens of an answer, outside any $...$ maths, trailing punctuation removed."""
    return {word.strip(".,;:()") for word in _MATH_SEGMENT.sub(" ", answer).split()}


def example_checks_out(final_answer: str, expression: str) -> bool:
    """SymPy evaluates the example's own expression and compares it with the printed answer.

    A numeric answer may be printed to 3 significant figures (Cambridge default); an algebraic one must be
    equivalent. A list ("the factors of 36: 1, 2, 3, ...") is compared value by value, in order or as a set. This
    catches arithmetic and algebra slips; it cannot tell whether the expression models the problem correctly,
    which is why examples also cite the textbook method they follow.
    """
    if not expression.strip() or not final_answer.strip():
        return False
    answers, expressions = _values(final_answer), _values(expression)
    if len(answers) > 1 or len(expressions) > 1:
        if len(answers) != len(expressions):
            return False
        if all(_one_value_checks_out(a, e) for a, e in zip(answers, expressions, strict=True)):
            return True
        remaining = list(expressions)  # same values in another order
        for answer in answers:
            match = next((e for e in remaining if _one_value_checks_out(answer, e)), None)
            if match is None:
                return False
            remaining.remove(match)
        return True
    return _one_value_checks_out(final_answer, expression)


def _one_value_checks_out(final_answer: str, expression: str) -> bool:
    try:
        exact = parse_math(expression)
    except MathParseError:
        return False
    numeric = NumericSpec(exact=expression, accuracy="sf", places=3)
    for reading in _readings(final_answer):
        try:
            if not exact.free_symbols and check_numeric(reading, numeric).status == "correct":
                return True
            if equivalent(reading, exact):
                return True
        except (MathParseError, TypeError, ValueError, ZeroDivisionError):
            continue
    return False


_X = sympy.Symbol("x")
_SOLVE = re.compile(r"\bsolve\b", re.IGNORECASE)
_DECIMALS = re.compile(r"^[+-]?\d+(?:\.(\d+))?$")


def _problem_equation(problem: str) -> sympy.Expr | None:
    """The equation in x an example asks her to solve, as one expression equal to zero: the last piece of maths in
    the problem with one "=", only the letter x, and not a graph's own equation ("y = ...")."""
    if not _SOLVE.search(problem):
        return None  # "find y when x = 3" substitutes; it does not set an equation to solve
    found = None
    for segment in _MATH_SEGMENT.findall(problem):
        if segment.count("=") != 1 or segment.strip().startswith("y"):
            continue
        left, right = segment.split("=")
        if left.strip() == "x" or right.strip() == "x":
            continue  # "x = 2.5" is a value she is given
        try:
            expr = parse_math(left) - parse_math(right)
        except (MathParseError, TypeError, ValueError):
            continue
        if expr.free_symbols == {_X}:
            found = expr
    return found


def _within(value: str, root: complex) -> bool:
    """A printed value stands for a root when it is within one unit in the last place it shows (a value read off a
    graph is as often cut short as rounded: 0.87 for 0.877), or within 1% when it shows no decimals."""
    match = _DECIMALS.match(value.strip())
    if match is None or abs(root.imag) > 1e-9:
        return False
    places = len(match.group(1) or "")
    tolerance = 10.0**-places if places else max(1e-2 * abs(root.real), 1e-9)
    return abs(float(value) - root.real) <= tolerance + 1e-12


def solves_problem(problem: str, final_answer: str) -> bool | None:
    """Does every value in the answer solve the equation the problem sets? True/False when the problem sets one
    polynomial equation in x and the answer is numbers; None when that cannot be judged here.

    `example_checks_out` only proves the printed answer equals the model's own expression. This checks the
    expression was the right one: "solve x^2 - 3x + 2 = x - 1" answered "1.3, 2.7" is wrong (the roots are 1 and 3)
    even though its own expression gives 1.3 and 2.7."""
    equation = _problem_equation(problem)
    if equation is None:
        return None
    try:
        poly = sympy.Poly(sympy.expand(equation), _X)
    except sympy.PolynomialError:
        return None
    if poly.degree() < 1:
        return None
    roots = [complex(r) for r in sympy.Poly(poly).nroots(n=15)]
    values = [_NAMED_VALUE.sub("", v).strip() for v in _values(final_answer)]
    if not values or not all(_DECIMALS.match(v) for v in values):
        return None
    return all(any(_within(v, r) for r in roots) for v in values)


_NAMED_VALUE = re.compile(r"^\s*x\s*=\s*")


# A run of maths in plain text ("x³ - 5x² - x + 14 = 0"): digits, x, powers, operators and brackets.
_PLAIN_MATH = re.compile(r"[0-9xX²³^+\-−*/×÷().\s=]{5,}")


def _polynomials(text: str) -> list[sympy.Poly]:
    """The non-trivial polynomials in x written in a text (degree two or more), each side of an equation taken as
    one polynomial (L − R) and also each side alone, scaled so the leading coefficient is 1."""
    pieces = [*_MATH_SEGMENT.findall(text), *_PLAIN_MATH.findall(_MATH_SEGMENT.sub(" ", text))]
    out = []
    for piece in pieces:
        if "x" not in piece.lower():
            continue
        sides = [s for s in piece.split("=") if s.strip()]
        candidates = list(sides)
        if len(sides) == 2:
            candidates.append(f"({sides[0]}) - ({sides[1]})")
        for candidate in candidates:
            try:
                expr = parse_math(candidate.strip().strip(".,;"))
                if expr.free_symbols != {_X}:
                    continue
                poly = sympy.Poly(sympy.expand(expr), _X)
            except (MathParseError, TypeError, ValueError, sympy.PolynomialError):
                continue
            if poly.degree() >= 2:
                out.append(poly.monic())
    return out


def reuses_past_paper_maths(text: str, past: Sequence[sympy.Poly]) -> bool:
    """True when a text writes the same curve or equation as a past-paper question (up to a constant factor):
    "the graph y = x^3 + 4x^2 - 2" taken from one question is the question, whatever the words around it."""
    if not past:
        return False
    return any(poly == other for poly in _polynomials(text) for other in past)


def guard(
    draft: LessonDraft,
    excerpts: Sequence[Excerpt],
    *,
    example_check: Literal["sympy", "none"],
    names_need_citation: bool,
    answer_units: bool = False,
    past_papers: Sequence[str] = (),
) -> GuardedLesson:
    draft = repair_draft(draft)
    past_ngrams = text_overlap.source_ngrams("\n".join(past_papers), PAST_PAPER_RUN) if past_papers else set()
    past_maths = [poly for question in past_papers for poly in _polynomials(question)]
    report = GuardReport()
    out = GuardedLesson(summary=" ".join(draft.summary.split()), report=report)

    def cited_text(numbers: Sequence[int]) -> str:
        return "\n".join(excerpts[n - 1].text for n in numbers)

    for section in draft.sections:
        numbers = _cited(section.sources, excerpts)
        if not numbers:
            report.dropped_uncited += 1
            continue
        if garbled(section.heading, section.body):
            report.dropped_garbled += 1
            continue
        sources = cited_text(numbers)
        if text_overlap.copies_source(section.body, text_overlap.source_ngrams(sources, COPY_RUN), COPY_RUN):
            report.dropped_copied += 1
            continue
        if (
            past_ngrams and text_overlap.copies_source(section.body, past_ngrams, PAST_PAPER_RUN)
        ) or reuses_past_paper_maths(section.body, past_maths):
            report.dropped_past_paper += 1
            continue
        if names_need_citation and unsupported_names(section.body, sources):
            report.dropped_unsupported_name += 1
            continue
        out.sections.append(
            {
                "heading": section.heading.strip(),
                "body": section.body.strip(),
                "sources": _source_refs(numbers, excerpts),
            }
        )
        report.kept_sections += 1

    for term in draft.key_terms:
        numbers = _cited(term.sources, excerpts)
        if (
            not numbers
            or garbled(term.term, term.meaning)
            or (names_need_citation and unsupported_names(term.meaning, cited_text(numbers)))
        ):
            report.dropped_terms += 1
            continue
        out.key_terms.append(
            {"term": term.term.strip(), "meaning": term.meaning.strip(), "sources": _source_refs(numbers, excerpts)}
        )

    for example in draft.worked_examples:
        numbers = _cited(example.sources, excerpts)
        checked: str | None = None
        if garbled(example.problem, example.final_answer, *example.steps):
            report.dropped_garbled += 1
            continue
        if (
            past_ngrams and text_overlap.copies_source(example.problem, past_ngrams, PAST_PAPER_RUN)
        ) or reuses_past_paper_maths(" ".join([example.problem, *example.steps]), past_maths):
            report.dropped_examples_past_paper += 1
            continue
        if example_check == "sympy":
            if not example.answer_expression.strip():
                report.dropped_examples_unchecked += 1
                continue
            if not example_checks_out(example.final_answer, example.answer_expression):
                report.dropped_examples_wrong += 1
                continue
            if solves_problem(example.problem, example.final_answer) is False:
                report.dropped_examples_wrong += 1
                continue
            checked = "sympy"
        unit = example.unit.strip()
        if answer_units:
            # A physical answer is not complete without its unit: one Pint does not recognise drops the example,
            # and an answer with no unit must say so ("none") rather than leave it blank.
            if units.is_no_unit(unit):
                unit = ""
            elif not units.is_unit(unit):
                report.dropped_examples_unit += 1
                continue
            elif units.display(unit) in _answer_words(example.final_answer):
                unit = ""  # "40 N to the right" already shows it; printing "N" again would read "... right N"
        else:
            unit = ""
        if (
            example_check != "sympy"
            and names_need_citation
            and unsupported_names(" ".join([example.problem, *example.steps]), cited_text(numbers))
        ):
            report.dropped_unsupported_name += 1
            continue
        out.worked_examples.append(
            {
                "problem": example.problem.strip(),
                "steps": [s.strip() for s in example.steps if s.strip()],
                "final_answer": example.final_answer.strip(),
                "unit": units.display(unit) if unit else "",
                "checked": checked,
                "sources": _source_refs(numbers, excerpts),
                "level": example.level.strip().lower() if example.level.strip().lower() in LEVELS else None,
            }
        )
        report.kept_examples += 1

    # The summary and pitfalls cite nothing of their own, so they are held against every excerpt given.
    everything = cited_text(range(1, len(excerpts) + 1))
    all_ngrams = text_overlap.source_ngrams(everything, COPY_RUN)

    def clean(text: str) -> bool:
        if garbled(text) or text_overlap.copies_source(text, all_ngrams, COPY_RUN):
            return False
        return not (names_need_citation and unsupported_names(text, everything))

    if not clean(out.summary):
        out.summary = ""
    out.pitfalls = [p.strip() for p in draft.pitfalls if p.strip() and clean(p)][:5]
    return out


CAPTION_MAX = 140
CAPTION_RUN = 8


def guard_diagrams(
    drafts: Sequence[DiagramDraft], sections: Sequence[dict], *, allowed: set[str], limit: int
) -> tuple[list[dict], dict[str, int]]:
    """Keep the diagrams that check out (docs/STUDENT-APP.md AC-U14).

    A diagram is kept only if its kind belongs to this subject, its numbers survive ``diagrams.check`` — which
    computes what is drawn rather than trusting the model — its caption is short, in our own words and attached
    to a section of this lesson, and its numbers are this lesson's own. That last rule matters: a model handed
    example data in its instructions will happily draw the example ("£60 shared 2:3") on a lesson about
    something else, and a picture about nothing is worse than no picture.
    """
    lesson_text = " ".join(
        [
            *(str(section.get("body", "")) for section in sections),
            *(str(section.get("heading", "")) for section in sections),
        ]
    )
    section_text = " ".join(str(section.get("body", "")) for section in sections)
    kept: list[dict] = []
    report = {
        "kept": 0,
        "dropped_kind": 0,
        "dropped_numbers": 0,
        "dropped_caption": 0,
        "dropped_uncited": 0,
        "dropped_ungrounded": 0,
    }
    for draft in drafts:
        if len(kept) >= limit:
            break
        caption = " ".join(repair_json_escapes(draft.caption).split())[:CAPTION_MAX]
        cited = [n for n in dict.fromkeys(draft.sources) if 0 < n <= len(sections)]
        if not cited:
            report["dropped_uncited"] += 1
            continue
        if not caption or garbled(caption) or copies_caption(caption, section_text):
            report["dropped_caption"] += 1
            continue
        try:
            checked = diagrams.check(draft.kind, draft.data, allowed=allowed)
        except diagrams.DiagramError:
            report["dropped_kind" if draft.kind not in allowed else "dropped_numbers"] += 1
            continue
        if draft.kind not in diagrams.ILLUSTRATIVE and not numbers_in_lesson(draft.data, lesson_text):
            report["dropped_ungrounded"] += 1
            continue
        if caption_disagrees(caption, checked.data):
            # "between -2 and 3" under a line shaded to 4 teaches the wrong thing twice over.
            report["dropped_caption"] += 1
            continue
        # Stored as a candidate: checks prove a picture's numbers, not that it teaches the right thing, so a
        # person approves it before she sees it (app.jobs.illustrate review).
        kept.append(
            {"kind": checked.kind, "caption": caption, "data": checked.data, "sections": cited, "approved": False}
        )
        report["kept"] += 1
    return kept, report


_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")


def numbers_in_lesson(data: dict, lesson_text: str) -> bool:
    """True if the diagram's own numbers are ones this lesson uses.

    Whole numbers up to ten are ignored as evidence: every lesson contains a "2" somewhere. A diagram with no
    numbers at all (nothing to ground) is allowed through — the other checks still apply.
    """
    proposed = {_clean(n) for n in _NUMBER_TOKEN.findall(str(data))}
    telling = {n for n in proposed if not (n.isdigit() and int(n) <= 10)}
    if not telling:
        return True
    present = {_clean(n) for n in _NUMBER_TOKEN.findall(lesson_text)}
    return bool(telling & present)


def _clean(number: str) -> str:
    return number.rstrip("0").rstrip(".") if "." in number else number


_SIGNED_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


_BETWEEN = re.compile(r"between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def _shading_disagrees(caption: str, data: dict) -> bool:
    """ "between -2 and 3" under a stretch shaded from -2 to 4 is a picture that teaches the wrong range."""
    match = _BETWEEN.search(caption)
    if not match or data.get("shade_from") is None or data.get("shade_to") is None:
        return False
    return (float(match.group(1)), float(match.group(2))) != (float(data["shade_from"]), float(data["shade_to"]))


def caption_disagrees(caption: str, data: dict) -> bool:
    """True if the caption names a number the picture does not contain — signs included, so "between -2 and 3"
    under a line shaded to 4 is caught. Ones and twos, and the angles of geometry, are too common to judge."""
    if _shading_disagrees(caption, data):
        return True
    drawn = {_clean(n) for n in _SIGNED_NUMBER.findall(str(data))}
    named = {_clean(n) for n in _SIGNED_NUMBER.findall(caption)}
    telling = {n for n in named if not (n.isdigit() and int(n) <= 2)} - {"90", "180", "360"}  # angles are geometry
    return bool(telling - drawn)


def copies_caption(caption: str, lesson_text: str) -> bool:
    """A caption repeating a run of the lesson's own words is a duplicate line, not a caption."""
    return text_overlap.copies_source(caption, text_overlap.source_ngrams(lesson_text, CAPTION_RUN), CAPTION_RUN)


_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")


def garbled(*texts: str) -> bool:
    """A control character left after repair: an unescaped backslash JSON decoding could not be traced back to a
    LaTeX command ("\\br" arrives as BACKSPACE + "r"). It would show as garbage, so the part is dropped."""
    return any(_CONTROL.search(t) for t in texts)


_CITATION_MARKER = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\]")
_MATH_OR_TEXT = re.compile(r"(\$[^$]*\$)")


def strip_markers(text: str) -> str:
    """Remove excerpt numbers the model wrote into the prose ("... on the x-axis. [1, 3]"); they belong in
    `sources`. Maths between dollar signs is left alone: "[1, 3]" there is an interval."""
    parts = _MATH_OR_TEXT.split(text)
    return "".join(p if p.startswith("$") else _CITATION_MARKER.sub("", p) for p in parts)


def repair_draft(draft: LessonDraft) -> LessonDraft:
    """Restore LaTeX commands that JSON decoding turned into control characters ("\\times" read as TAB + "imes")
    before anything is checked or stored, and drop excerpt numbers written into the prose. Low-cost models leave
    the backslashes unescaped."""

    def fix(text: str) -> str:
        return strip_markers(repair_json_escapes(text))

    return LessonDraft(
        summary=fix(draft.summary),
        sections=[s.model_copy(update={"heading": fix(s.heading), "body": fix(s.body)}) for s in draft.sections],
        key_terms=[t.model_copy(update={"term": fix(t.term), "meaning": fix(t.meaning)}) for t in draft.key_terms],
        worked_examples=[
            e.model_copy(
                update={
                    "problem": fix(e.problem),
                    "steps": [fix(x) for x in e.steps],
                    "final_answer": fix(e.final_answer),
                    "answer_expression": fix(e.answer_expression),
                    "unit": fix(e.unit),
                }
            )
            for e in draft.worked_examples
        ],
        pitfalls=[fix(p) for p in draft.pitfalls],
    )


def repair_content(content: dict) -> tuple[dict, bool]:
    """The same repair for a lesson already stored. Returns the content and whether anything changed."""

    def fix(text: str) -> str:
        return strip_markers(repair_json_escapes(text))

    repaired = {
        **content,
        "summary": fix(content.get("summary", "")),
        "sections": [{**x, "heading": fix(x["heading"]), "body": fix(x["body"])} for x in content.get("sections", [])],
        "key_terms": [
            {**x, "term": fix(x["term"]), "meaning": fix(x["meaning"])} for x in content.get("key_terms", [])
        ],
        "worked_examples": [
            {
                **x,
                "problem": fix(x["problem"]),
                "steps": [fix(s) for s in x["steps"]],
                "final_answer": fix(x["final_answer"]),
            }
            for x in content.get("worked_examples", [])
        ],
        "pitfalls": [fix(p) for p in content.get("pitfalls", [])],
    }
    return repaired, repaired != content


def drop_unsolved(content: dict) -> tuple[dict, int]:
    """Remove stored worked examples whose answer does not solve the equation their problem sets (guard v7)."""
    kept = [
        x
        for x in content.get("worked_examples", [])
        if x.get("checked") != "sympy" or solves_problem(x["problem"], x["final_answer"]) is not False
    ]
    removed = len(content.get("worked_examples", [])) - len(kept)
    return ({**content, "worked_examples": kept} if removed else content), removed


def drop_garbled(content: dict) -> tuple[dict, int]:
    """Remove stored parts that still hold a control character after repair. Returns content and parts removed."""
    sections = [x for x in content.get("sections", []) if not garbled(x["heading"], x["body"])]
    terms = [x for x in content.get("key_terms", []) if not garbled(x["term"], x["meaning"])]
    examples = [
        x for x in content.get("worked_examples", []) if not garbled(x["problem"], x["final_answer"], *x["steps"])
    ]
    pitfalls = [p for p in content.get("pitfalls", []) if not garbled(p)]
    summary = "" if garbled(content.get("summary", "")) else content.get("summary", "")
    removed = (
        len(content.get("sections", []))
        - len(sections)
        + len(content.get("key_terms", []))
        - len(terms)
        + len(content.get("worked_examples", []))
        - len(examples)
        + len(content.get("pitfalls", []))
        - len(pitfalls)
        + (summary != content.get("summary", ""))
    )
    cleaned = {**content, "summary": summary, "sections": sections, "key_terms": terms}
    return {**cleaned, "worked_examples": examples, "pitfalls": pitfalls}, removed


def recheck_names(content: dict, texts: dict[str, str]) -> tuple[dict, int]:
    """Apply the name rule to a stored lesson without the model: drop sections, terms and examples naming
    something their cited excerpts do not contain. Returns the content and how many parts were removed."""
    removed = 0

    def ok(text: str, sources: list[dict]) -> bool:
        return not unsupported_names(text, "\n".join(texts.get(src["chunk_id"], "") for src in sources))

    kept_sections = [x for x in content.get("sections", []) if ok(x["body"], x["sources"])]
    kept_terms = [x for x in content.get("key_terms", []) if ok(x["meaning"], x["sources"])]
    kept_examples = [
        x for x in content.get("worked_examples", []) if ok(" ".join([x["problem"], *x["steps"]]), x.get("sources", []))
    ]
    everything = "\n".join(texts.values())
    summary = content.get("summary", "")
    if summary and unsupported_names(summary, everything):
        summary, removed = "", removed + 1
    pitfalls = [p for p in content.get("pitfalls", []) if not unsupported_names(p, everything)]
    removed += (
        len(content.get("sections", []))
        - len(kept_sections)
        + len(content.get("key_terms", []))
        - len(kept_terms)
        + len(content.get("worked_examples", []))
        - len(kept_examples)
        + len(content.get("pitfalls", []))
        - len(pitfalls)
    )
    return (
        {
            **content,
            "summary": summary,
            "sections": kept_sections,
            "key_terms": kept_terms,
            "worked_examples": kept_examples,
            "pitfalls": pitfalls,
        },
        removed,
    )
