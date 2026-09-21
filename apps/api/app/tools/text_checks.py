"""Deterministic checks on written answers (subject config tools: word_count, command_word_check)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")
_CONCLUSION = re.compile(
    r"\b(in conclusion|to conclude|overall|on balance|in summary|therefore,? i (?:think|believe))\b", re.I
)
# Command words that expect a judgement, so an answer without a conclusion cannot reach the top level.
JUDGEMENT_COMMANDS = frozenset({"evaluate", "to what extent", "assess", "discuss"})
MIN_WORDS_PER_MARK = 6  # below this an extended answer is almost certainly underdeveloped


@dataclass(frozen=True)
class TextChecks:
    word_count: int
    command_word: str | None
    too_short: bool
    judgement_expected: bool
    conclusion_present: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def normalise_command_word(command_word: str | None, stem: str = "") -> str | None:
    if command_word:
        return command_word.strip().lower()
    lowered = stem.strip().lower()
    if lowered.startswith("to what extent"):
        return "to what extent"
    first = _WORD.findall(lowered[:40])
    return first[0] if first else None


def check_answer(answer: str, *, marks: int, command_word: str | None, stem: str = "") -> TextChecks:
    words = word_count(answer)
    command = normalise_command_word(command_word, stem)
    judgement = command in JUDGEMENT_COMMANDS and marks >= 8
    return TextChecks(
        word_count=words,
        command_word=command,
        too_short=marks >= 4 and words < marks * MIN_WORDS_PER_MARK,
        judgement_expected=judgement,
        conclusion_present=bool(_CONCLUSION.search(answer or "")),
    )
