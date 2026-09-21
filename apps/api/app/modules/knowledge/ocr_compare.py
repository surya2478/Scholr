"""Compare two transcriptions of the same page, to screen low-cost models for OCR roles.

The reference is another model's output, not ground truth. Metrics:
- content_f1: same words and numbers captured, whatever the notation (LaTeX or Unicode) — the content test.
- word_f1 / math_f1: prose outside $...$ and LaTeX tokens inside it — these also move when the *style* differs.
- unicode_leaks: Unicode maths characters left outside $...$ in the candidate (should be 0 for maths pages).
- math segments: how much of the page the candidate put in LaTeX compared with the reference.
Disagreements are settled by looking at the page, not by trusting either model.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean

_FIGURE = re.compile(r"\[Figure:[^\]]*\]", re.IGNORECASE)
_MATH = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.DOTALL)
_WORD = re.compile(r"[a-z0-9]+")
_CONTENT_TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)?")
_LATEX_COMMAND = re.compile(r"\\[a-zA-Z]+")
_LATEX_TOKEN = re.compile(r"\\[a-zA-Z]+|\d+(?:\.\d+)?|[a-zA-Z]|[^\s{}]")
_LATEX_SYNONYMS = ((r"\dfrac", r"\frac"), (r"\tfrac", r"\frac"), (r"\left", ""), (r"\right", ""), (r"\,", ""))
_SCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")
_VULGAR = {"½": " 1 2 ", "¼": " 1 4 ", "¾": " 3 4 ", "⅓": " 1 3 ", "⅔": " 2 3 "}
UNICODE_MATH_CHARS = frozenset("²³¹⁰⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉×÷√π°≤≥≠≈±½¼¾⅓⅔∠")


def _f1(reference: Counter[str], candidate: Counter[str]) -> float:
    ref_total, cand_total = sum(reference.values()), sum(candidate.values())
    if ref_total == 0 and cand_total == 0:
        return 1.0
    overlap = sum((reference & candidate).values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / cand_total, overlap / ref_total
    return 2 * precision * recall / (precision + recall)


def content_tokens(markdown: str) -> Counter[str]:
    text = _FIGURE.sub(" ", markdown)
    for char, spelled in _VULGAR.items():
        text = text.replace(char, spelled)
    text = _LATEX_COMMAND.sub(" ", text.translate(_SCRIPT_DIGITS)).lower()
    return Counter(_CONTENT_TOKEN.findall(text))


def math_segments(markdown: str) -> list[str]:
    return [display or inline for display, inline in _MATH.findall(_FIGURE.sub("", markdown))]


def math_tokens(markdown: str) -> Counter[str]:
    tokens: Counter[str] = Counter()
    for segment in math_segments(markdown):
        for old, new in _LATEX_SYNONYMS:
            segment = segment.replace(old, new)
        tokens.update(_LATEX_TOKEN.findall(segment))
    return tokens


def prose_words(markdown: str) -> Counter[str]:
    text = _MATH.sub(" ", _FIGURE.sub(" ", markdown)).lower()
    return Counter(_WORD.findall(text))


def unicode_leaks(markdown: str) -> int:
    return sum(1 for char in _MATH.sub(" ", markdown) if char in UNICODE_MATH_CHARS)


# JSON-escape damage: "\times" decoded as TAB + "imes", "\frac" as FORM FEED + "rac", "\beta" as BACKSPACE + "eta".
_ESCAPE_DAMAGE = re.compile(
    r"\t(?=ext|imes|heta|frac|au\b|an\b)|\x0c(?=rac|orall)|\x08(?=egin|eta|ar\b|ig|oxed|inom)|\r(?=ight|ho\b|angle)"
)
_SEGMENT_NORMALISE = (
    (r"\dfrac", r"\frac"),
    (r"\tfrac", r"\frac"),
    (r"\left", ""),
    (r"\right", ""),
    (r"\leq", r"\le"),
    (r"\geq", r"\ge"),
    (r"\neq", r"\ne"),
    (r"\text", ""),
    (r"\mathrm", ""),
    (r"\,", ""),
    (r"\ ", ""),
    (r"\!", ""),
    ("{", ""),
    ("}", ""),
)


def escape_damage(markdown: str) -> int:
    return len(_ESCAPE_DAMAGE.findall(markdown))


def normalised_segments(markdown: str) -> Counter[str]:
    segments: Counter[str] = Counter()
    for segment in math_segments(markdown):
        for old, new in _SEGMENT_NORMALISE:
            segment = segment.replace(old, new)
        segments[re.sub(r"\s+", "", segment)] += 1
    return segments


@dataclass(frozen=True)
class PageComparison:
    page_number: int
    content_f1: float
    word_f1: float
    math_f1: float | None  # None when neither transcription contains LaTeX
    math_recall: float | None  # share of reference LaTeX expressions reproduced exactly; None if reference has none
    unicode_leaks: int
    escape_damage: int
    reference_math_segments: int
    candidate_math_segments: int


def compare(page_number: int, reference: str, candidate: str) -> PageComparison:
    ref_math, cand_math = math_tokens(reference), math_tokens(candidate)
    ref_segments, cand_segments = normalised_segments(reference), normalised_segments(candidate)
    ref_total = sum(ref_segments.values())
    return PageComparison(
        page_number=page_number,
        content_f1=round(_f1(content_tokens(reference), content_tokens(candidate)), 4),
        word_f1=round(_f1(prose_words(reference), prose_words(candidate)), 4),
        math_f1=round(_f1(ref_math, cand_math), 4) if (ref_math or cand_math) else None,
        math_recall=round(sum((ref_segments & cand_segments).values()) / ref_total, 4) if ref_total else None,
        unicode_leaks=unicode_leaks(candidate),
        escape_damage=escape_damage(candidate),
        reference_math_segments=ref_total,
        candidate_math_segments=sum(cand_segments.values()),
    )


@dataclass(frozen=True)
class ComparisonSummary:
    pages: int
    mean_content_f1: float
    min_content_f1: float
    mean_word_f1: float
    mean_math_f1: float | None
    mean_math_recall: float | None
    unicode_leaks: int
    escape_damage: int
    math_segment_ratio: float | None  # candidate / reference LaTeX segments over the sample
    verdict: str  # "candidate_ok" | "review"


# Screening thresholds. Passing is necessary, not sufficient: spot-check the lowest pages by eye.
CONTENT_F1_MEAN, CONTENT_F1_MIN, MATH_SEGMENT_RATIO_MIN = 0.95, 0.85, 0.7


def summarise(rows: Sequence[PageComparison]) -> ComparisonSummary:
    if not rows:
        raise ValueError("no pages compared")
    content = [r.content_f1 for r in rows]
    maths = [r.math_f1 for r in rows if r.math_f1 is not None]
    recalls = [r.math_recall for r in rows if r.math_recall is not None]
    ref_segments = sum(r.reference_math_segments for r in rows)
    ratio = round(sum(r.candidate_math_segments for r in rows) / ref_segments, 3) if ref_segments else None
    leaks = sum(r.unicode_leaks for r in rows)
    damage = sum(r.escape_damage for r in rows)
    ok = (
        mean(content) >= CONTENT_F1_MEAN
        and min(content) >= CONTENT_F1_MIN
        and leaks == 0
        and damage == 0
        and (ratio is None or ratio >= MATH_SEGMENT_RATIO_MIN)
    )
    return ComparisonSummary(
        pages=len(rows),
        mean_content_f1=round(mean(content), 4),
        min_content_f1=min(content),
        mean_word_f1=round(mean(r.word_f1 for r in rows), 4),
        mean_math_f1=round(mean(maths), 4) if maths else None,
        mean_math_recall=round(mean(recalls), 4) if recalls else None,
        unicode_leaks=leaks,
        escape_damage=damage,
        math_segment_ratio=ratio,
        verdict="candidate_ok" if ok else "review",
    )
