"""Deterministic check that generated text is our own words, not a copy of its source (copyright).

Used wherever a model writes from copyrighted material: examiner reports (AC-R6) and textbook-grounded lessons
(docs/STUDENT-APP.md AC-U4). A point or section sharing a run of ``n`` consecutive words with its source is a copy.
"""

from __future__ import annotations

import re


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("’", "'"))


def source_ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    w = words(text)
    return {tuple(w[i : i + n]) for i in range(len(w) - n + 1)}


def copies_source(text: str, ngrams: set[tuple[str, ...]], n: int) -> bool:
    w = words(text)
    return any(tuple(w[i : i + n]) in ngrams for i in range(len(w) - n + 1))
