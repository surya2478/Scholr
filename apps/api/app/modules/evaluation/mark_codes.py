"""What Cambridge mark-scheme codes mean, in words a student can use (improvement 6, mark-scheme literacy).

The notation is Cambridge's own, shared across its mark schemes (CONTEXT: "M, A, B, SC, FT, isw, oe, cao, dep,
nfww, soi" in the 0580 mark schemes). Knowing that a method mark is given for working, even when the answer is then
wrong, is the whole reason to show working; so each mark she is shown says what kind of mark it is.

Deterministic: a code's kind comes from its letters, never from a model. A code that is not one of these (a marker
sometimes writes only "1") gets no meaning rather than a guessed one.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

MEANINGS: dict[str, str] = {
    "M": "Method mark: for a correct method, even if the answer that follows is wrong.",
    "A": "Accuracy mark: for a correct answer or step. It usually needs the method mark before it.",
    "B": "Independent mark: for a correct answer or statement, whatever the method.",
    "SC": "Special case: part credit the mark scheme allows for a common near-miss.",
    "FT": "Follow through: credit for correct work that uses your own earlier answer.",
}
_CODE = re.compile(r"^(SC|FT|M|A|B)\d*$", re.IGNORECASE)


def kind(code: str) -> str | None:
    match = _CODE.match((code or "").strip())
    return match.group(1).upper() if match else None


def meaning(code: str) -> str | None:
    found = kind(code)
    return MEANINGS.get(found) if found else None


def method_note(awards: Sequence[dict[str, Any]]) -> str | None:
    """When working earned a method mark but an accuracy mark was lost, say so: it is the lesson of the answer."""
    method = [a["code"] for a in awards if kind(a.get("code", "")) == "M" and a.get("awarded")]
    lost_accuracy = any(kind(a.get("code", "")) == "A" and not a.get("awarded") for a in awards)
    if not method or not lost_accuracy:
        return None
    marks = " and ".join(dict.fromkeys(method))
    return (
        f"Your working earned {marks} even though the final answer was not right. Method marks are given only for "
        "working you write down, so always show it."
    )
