"""Deterministic repairs for text returned by LLMs inside JSON.

Low-cost models often put LaTeX in JSON strings without escaping backslashes. After JSON decoding, "\\times"
arrives as TAB + "imes", "\\frac" as FORM FEED + "rac", "\\begin" as BACKSPACE + "egin", "\\right" as
CARRIAGE RETURN + "ight". Only those unambiguous command tails are restored; ordinary tabs and newlines are left alone.
"""

from __future__ import annotations

import re

_DAMAGED_ESCAPES = (
    (re.compile(r"\t(?=ext|imes|heta|frac|au\b|an\b)"), r"\\t"),
    (re.compile(r"\x0c(?=rac|orall)"), r"\\f"),
    (re.compile(r"\x08(?=egin|eta|ar\b|ig|oxed|inom)"), r"\\b"),
    (re.compile(r"\r(?=ight|ho\b|angle)"), r"\\r"),
)


def repair_json_escapes(text: str) -> str:
    for pattern, replacement in _DAMAGED_ESCAPES:
        text = pattern.sub(replacement, text)
    return text
