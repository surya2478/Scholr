"""What a question is called on her screen (docs/STUDENT-APP.md AC-U13).

A bank item's `source_ref` is a key, not a name: "0580/21/MJ25/Q17(b)(ii)" or "template/round_three_sf/0". The
first says something useful to a student sitting the exam — which paper it came from — and the second says
nothing at all. This turns the first into English and drops the second.
"""

from __future__ import annotations

import re

SESSIONS = {"MJ": "June", "ON": "November", "FM": "March"}
PRACTICE = "Practice question"
_PAST_PAPER = re.compile(r"^(?P<syllabus>\d{4})/(?P<paper>\w+)/(?P<session>[A-Z]{2})(?P<year>\d{2})/(?P<q>.+)$")


def item_label(source_ref: str | None, origin: str) -> str:
    """ "June 2025 · Paper 21 · Q17(b)(ii)" for a past paper, "Practice question" for anything generated."""
    if origin != "past_paper" or not source_ref:
        return PRACTICE
    match = _PAST_PAPER.match(source_ref.strip())
    if match is None:
        return source_ref.strip()  # an unfamiliar shape is shown as it is, never guessed at
    session = SESSIONS.get(match["session"])
    when = f"{session} 20{match['year']}" if session else f"20{match['year']}"
    return f"{when} · Paper {match['paper']} · {match['q']}"
