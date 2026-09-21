"""Examiner reports -> per-question segments, and the guard on what may be kept from them (AC-R6).

A Principal Examiner Report for Teachers covers every component of a syllabus in one PDF, laid out the same
way for Maths and Sociology: ``Paper 0495/11``, then key messages and general comments, then "Comments on
specific questions" with ``Question 2 Identity: self and society`` headings and ``(a)``/``(a) (i)``/``(ii)``
part labels at the start of a line.

Splitting on that layout is done here, in code, so which question an insight belongs to is never the model's
guess. The model only paraphrases a segment it is handed (prompt ``examiner_report_extract``); ``guard``
then drops anything it copied, because the reports are UCLES copyright held for private study and only our
own short wording is stored.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.llm.gateway import CallContext, LLMGateway
from app.modules.assessment.past_papers import normalise_ref
from app.tools import text_overlap

SEGMENTER_VERSION = "er-seg-v1"

ROMANS = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x")
LETTERS = "abcdefghijklmnopqrstuvwxyz"

_PAPER = re.compile(r"^Paper\s+(\d{4})/(\d{2})$")
_SPECIFIC = re.compile(r"^comments\s+on\s+specific\s+questions", re.I)
# A heading is short and is not a sentence: "Question 3 Crime, Deviance and Social Control", never
# "Question 3 those that did made a good attempt..." (a wrapped prose line) or "Questions 12, 13 and 25(b).".
_QUESTION = re.compile(r"^Question\s+(\d{1,2})(?:\s+([A-Z(‘'\"][^.]{0,50}))?$")
_PART = re.compile(r"^\(([a-z]{1,4})\)\s*(?:\(([ivx]{1,4})\))?(?:\s+(.*))?$")
_RUNNING_HEAD = re.compile(
    r"^(Cambridge International|Principal Examiner Report|\d{4}\s+\w[\w ]*\s(June|November|March)\s+\d{4}$|"
    r"(©|�)\s*\d{4}$|[A-Z][A-Z ]{3,40}$)"
)

# Kept points must be our own words: any run of this many words taken from the report drops the point.
MAX_SHARED_WORDS = 8
MAX_POINT_WORDS = 40
KINDS = ("common_error", "what_scored", "advice")


@dataclass(frozen=True)
class ReportSegment:
    syllabus_code: str
    component: str
    question_ref: str | None  # normalised ("1(a)(ii)"); None = the paper's key messages and general comments
    text: str
    pages: tuple[int, ...]

    @property
    def key(self) -> str:
        return f"{self.component}:{self.question_ref or 'paper'}"

    @property
    def question_number(self) -> str | None:
        return None if self.question_ref is None else re.match(r"\d+", self.question_ref).group(0)  # type: ignore[union-attr]

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


@dataclass
class _Open:
    syllabus_code: str
    component: str
    question: str | None = None
    letter: str | None = None
    roman: str | None = None
    lines: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)

    @property
    def ref(self) -> str | None:
        if self.question is None:
            return None
        return self.question + (f"({self.letter})" if self.letter else "") + (f"({self.roman})" if self.roman else "")


def _is_roman_step(token: str, state: _Open) -> bool:
    """Is ``(token)`` the next sub-part rather than a new lettered part? ``(i)`` after ``(a)`` is a roman
    sub-part; ``(i)`` after ``(h)`` with no sub-parts open is part (i)."""
    if token not in ROMANS:
        return False
    if state.letter is None:
        return True
    current = ROMANS.index(state.roman) if state.roman else -1
    if ROMANS.index(token) <= current:
        return False
    next_letter = LETTERS[LETTERS.index(state.letter) + 1] if state.letter != "z" else None
    return not (state.roman is None and len(token) == 1 and token == next_letter)


def _letter_advances(token: str, state: _Open) -> bool:
    return len(token) == 1 and (state.letter is None or LETTERS.index(token) > LETTERS.index(state.letter))


def segment_report(pages: Mapping[int, str], *, min_chars: int = 40) -> list[ReportSegment]:
    """Split one report's page texts into paper-level and per-part segments, in reading order.

    Part labels must move forward within a question (``(c)`` after ``(b)``, ``(ii)`` after ``(i)``), so a line
    of prose that happens to open with a back-reference like ``(a)`` is left as prose.
    """
    segments: list[ReportSegment] = []
    state: _Open | None = None
    in_questions = False

    def close() -> None:
        if state is None:
            return
        text = re.sub(r"[ \t]+", " ", "\n".join(state.lines)).strip()
        if len(text) >= min_chars:
            segments.append(
                ReportSegment(state.syllabus_code, state.component, state.ref, text, tuple(sorted(set(state.pages))))
            )
        state.lines, state.pages = [], []

    for page_number in sorted(pages):
        for raw in pages[page_number].splitlines():
            line = raw.strip()
            if not line or _RUNNING_HEAD.match(line):
                continue
            if m := _PAPER.match(line):
                close()
                state = _Open(m.group(1), m.group(2))
                in_questions = False
                continue
            if state is None:
                continue
            if _SPECIFIC.match(line):
                close()
                in_questions = True
                continue
            if in_questions and (m := _QUESTION.match(line)):
                close()
                state.question, state.letter, state.roman = m.group(1), None, None
                continue
            if in_questions and state.question is not None and (m := _PART.match(line)):
                first, second, rest = m.group(1), m.group(2), m.group(3) or ""
                if second and len(first) == 1 and _letter_advances(first, state):
                    close()
                    state.letter, state.roman = first, second
                    line = rest
                elif not second and _is_roman_step(first, state):
                    close()
                    state.roman = first
                    line = rest
                elif not second and _letter_advances(first, state):
                    close()
                    state.letter, state.roman = first, None
                    line = rest
                if not line:
                    continue
            state.lines.append(line)
            state.pages.append(page_number)
    close()
    # Only refs the question bank could hold are kept: anything else would never match an item.
    return [s for s in segments if s.question_ref is None or normalise_ref(s.question_ref) == s.question_ref]


def item_ref(syllabus_code: str, component: str, series: str, question_ref: str) -> str:
    """The ``question_item.source_ref`` a segment's insights attach to ("0495/11/MJ25/Q1(a)(ii)")."""
    return f"{syllabus_code}/{component}/{series}/Q{question_ref}"


def ancestor_refs(source_ref: str) -> list[str]:
    """``.../Q1(a)(ii)`` -> [``.../Q1(a)(ii)``, ``.../Q1(a)``, ``.../Q1``]: comments on a whole question or part
    apply to every sub-part under it."""
    head, _, ref = source_ref.rpartition("/Q")
    if not head:
        return [source_ref]
    parts = re.findall(r"^\d+|\([^)]*\)", ref)
    return [f"{head}/Q{''.join(parts[:n])}" for n in range(len(parts), 0, -1)]


# ---------------------------------------------------------------------------
# Guard: our own short words, never the report's
# ---------------------------------------------------------------------------


def _words(text: str) -> list[str]:
    return text_overlap.words(text)


def source_ngrams(text: str, n: int = MAX_SHARED_WORDS) -> set[tuple[str, ...]]:
    return text_overlap.source_ngrams(text, n)


def copies_source(point: str, ngrams: set[tuple[str, ...]], n: int = MAX_SHARED_WORDS) -> bool:
    return text_overlap.copies_source(point, ngrams, n)


def refs_mentioned(text: str) -> set[str]:
    """Question references written in a paper-level comment ("In Question 1(e) the justifications...")."""
    found = set()
    for m in re.finditer(r"Questions?\s+(\d{1,2}\s*(?:\(\s*[a-z]{1,4}\s*\)\s*)*)", text):
        ref = normalise_ref(m.group(1))
        if ref:
            found.add(ref)
    return found


@dataclass(frozen=True)
class KeptPoint:
    question_ref: str | None
    kind: str
    text: str


@dataclass
class GuardResult:
    kept: list[KeptPoint] = field(default_factory=list)
    copied: int = 0
    too_long: int = 0
    bad_ref: int = 0
    duplicate: int = 0


def guard(
    segment: ReportSegment,
    points: Iterable[tuple[str, str, str | None]],
    *,
    known_refs: Sequence[str] = (),
) -> GuardResult:
    """Keep (kind, text, ref) points that are short, our own words, and attributable.

    A point from a question segment belongs to that segment's ref, whatever the model says. A point from the
    paper-level segment may name a question only if the report itself names it there and the report has that
    question; otherwise it stays paper-level.
    """
    result = GuardResult()
    ngrams = source_ngrams(segment.text)
    mentioned = refs_mentioned(segment.text) if segment.question_ref is None else set()
    seen: set[str] = set()
    for kind, text, ref in points:
        text = " ".join(text.split())
        if kind not in KINDS or not text:
            continue
        if len(_words(text)) > MAX_POINT_WORDS:
            result.too_long += 1
            continue
        if copies_source(text, ngrams):
            result.copied += 1
            continue
        target = segment.question_ref
        if segment.question_ref is None and ref:
            normalised = normalise_ref(ref)
            if normalised and normalised in mentioned and normalised in known_refs:
                target = normalised
            else:
                result.bad_ref += 1
        folded = " ".join(_words(text))
        if folded in seen:
            result.duplicate += 1
            continue
        seen.add(folded)
        result.kept.append(KeptPoint(target, kind, text))
    return result


# ---------------------------------------------------------------------------
# Paraphrase (the only model step)
# ---------------------------------------------------------------------------

ROLE = "examiner_report_extractor"
PROMPT = "examiner_report_extract"


class _Point(BaseModel):
    model_config = ConfigDict(extra="ignore")

    block: str
    kind: Literal["common_error", "what_scored", "advice"]
    text: str
    question_ref: str = ""


class ReportExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    points: list[_Point] = Field(default_factory=list)


@dataclass
class Paraphrased:
    by_segment: dict[str, list[tuple[str, str, str | None]]]
    unknown_blocks: int
    model: str
    prompt_version: str
    cost_usd: float


def paraphrase(
    gateway: LLMGateway,
    ctx: CallContext,
    *,
    paper_label: str,
    segments: Sequence[ReportSegment],
    models: Sequence[str] | None = None,
) -> Paraphrased:
    """One call for a group of segments (one question's parts, or a paper's general comments).

    The model answers per block id; a point for an id it was not given is dropped, so it cannot move a
    comment onto another question.
    """
    blocks = "\n\n".join(f'<block id="{seg.key}">\n{seg.text}\n</block>' for seg in segments)
    result = gateway.structured(
        ROLE, PROMPT, {"paper_label": paper_label, "blocks": blocks}, ReportExtraction, ctx, models=models
    )
    by_segment: dict[str, list[tuple[str, str, str | None]]] = {seg.key: [] for seg in segments}
    unknown = 0
    for point in result.value.points:
        if point.block not in by_segment:
            unknown += 1
            continue
        by_segment[point.block].append((point.kind, point.text, point.question_ref or None))
    return Paraphrased(by_segment, unknown, result.model, result.prompt_version, result.cost_usd or 0.0)
