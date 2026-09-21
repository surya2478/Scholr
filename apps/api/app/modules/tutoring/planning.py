"""Essay-plan guards (Phase 2, AC-R5). Pure, no LLM.

A plan helps her write; a draft writes for her. The line between them cannot be left to a prompt, because a
prompt is a request and a model can decline to honour it. These checks run on every plan the model returns
and strip — or reject — anything she could lift into an exam script.

What makes a note a draft:

* length — a twelve-word note is a prompt to think; a thirty-word sentence is a sentence;
* prose joinery — "however", "this shows that", "in conclusion" exist to bind paragraphs, not notes;
* sentence shape — several sentences of continuous prose in one "point" is a paragraph wearing a disguise;
* who the words are about — "Weigh owner control against audience demand" is an instruction to herself and
  earns nothing if copied out; "Owners control what appears in the news" is a claim she could hand in. The
  first has no subject. That distinction matters more than length;
* shape on the page — length alone is not enough. "The family performs several important functions in
  modern industrial society" is eleven words, one sentence and no connective, yet it is a line she could
  hand in. Real revision notes are either very short or visibly structured — "Parsons — socialisation
  function", "Feminist critique: unpaid labour". So a note beyond a handful of words has to carry a dash,
  colon or comma; continuous prose does not.

The rule fails closed: anything that looks like prose is dropped, and a plan left with nothing usable is a
failure to be reported rather than a plan to be shown.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

RULE_VERSION = "essay_plan_v1"

# A note is a fragment. Beyond this it stops being something she has to turn into prose herself.
MAX_NOTE_WORDS = 14
# Beyond this a note has to look like a note — carrying a dash, colon or comma — rather than run on as a
# sentence. Below it, a bare fragment ("Define nuclear family early") is fine.
MAX_PLAIN_WORDS = 8
NOTE_PUNCTUATION = ("—", "–", "-", ":", ";", ",", "(", "/")
# A note that opens with one of these is an instruction to herself — "Weigh X against Y", "Link back to the
# question". It has no subject, so it is not a sentence she could hand in, however many words it runs to.
# Declarative prose ("Owners control content...") is untouched by this, which is the case that matters.
NOTE_OPENERS = frozenset(
    {
        "weigh",
        "compare",
        "contrast",
        "link",
        "balance",
        "define",
        "consider",
        "include",
        "use",
        "mention",
        "name",
        "avoid",
        "check",
        "note",
        "start",
        "structure",
        "judge",
        "support",
        "remember",
        "plan",
        "cover",
        "address",
        "distinguish",
        "outline",
        "explain",
        "describe",
        "evaluate",
        "discuss",
        "give",
        "state",
        "identify",
        "show",
        "apply",
        "develop",
        "finish",
    }
)


def opens_as_an_instruction(text: str) -> bool:
    words = _WORD.findall(text)
    if not words:
        return False
    first = words[0].lower()
    # "Weighing" and "weighs" are the same instruction as "weigh".
    for suffix in ("ing", "es", "s"):
        if first.endswith(suffix) and first[: -len(suffix)] in NOTE_OPENERS:
            return True
    return first in NOTE_OPENERS


# Discursive connectives: their only job is to join finished prose.
PROSE_MARKERS = re.compile(
    r"\b(however|furthermore|moreover|in conclusion|to conclude|firstly|secondly|finally|"
    r"this (?:shows|suggests|means|demonstrates)|it can be argued|on the other hand|"
    r"in summary|overall,|therefore,|thus,|consequently)\b",
    re.I,
)
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def sentence_count(text: str) -> int:
    return len(_SENTENCE_END.findall((text or "").strip()))


def is_draft(note: str) -> bool:
    """True when this 'note' is really a piece of the answer."""
    text = (note or "").strip()
    if not text:
        return True
    words = word_count(text)
    if words > MAX_NOTE_WORDS:
        return True
    if PROSE_MARKERS.search(text):
        return True
    if sentence_count(text) >= 2:
        return True
    if words <= MAX_PLAIN_WORDS or any(mark in text for mark in NOTE_PUNCTUATION):
        return False
    # A run of plain words is a sentence — unless it is an instruction to herself, which has no subject.
    return not opens_as_an_instruction(text)


@dataclass(frozen=True)
class GuardReport:
    kept: tuple[str, ...]
    dropped: tuple[str, ...]

    @property
    def any_kept(self) -> bool:
        return bool(self.kept)


def guard_notes(notes: Sequence[str], *, limit: int = 8) -> GuardReport:
    kept: list[str] = []
    dropped: list[str] = []
    for note in notes:
        text = (note or "").strip().rstrip(".")
        if not text:
            continue
        (dropped if is_draft(text) else kept).append(text)
    return GuardReport(tuple(kept[:limit]), tuple(dropped))


@dataclass(frozen=True)
class PlanDraft:
    """What the model proposed, before guarding."""

    for_points: Sequence[str]
    against_points: Sequence[str]
    evidence: Sequence[str]
    conclusion_direction: str
    watch_out: Sequence[str]
    refusal: str = ""


@dataclass(frozen=True)
class GuardedPlan:
    for_points: tuple[str, ...]
    against_points: tuple[str, ...]
    evidence: tuple[str, ...]
    conclusion_direction: str
    watch_out: tuple[str, ...]
    refusal: str
    dropped: int
    # What was removed. A guard whose decisions cannot be inspected is a guard nobody can calibrate — this
    # is what tells an eval whether it is catching drafts or eating good notes.
    dropped_notes: tuple[str, ...] = ()
    rule_version: str = RULE_VERSION

    @property
    def usable(self) -> bool:
        """A plan with no points left is not a plan she can work from."""
        return bool(self.for_points or self.against_points)


def guard(draft: PlanDraft) -> GuardedPlan:
    for_points = guard_notes(draft.for_points)
    against_points = guard_notes(draft.against_points)
    watch_out = guard_notes(draft.watch_out, limit=3)
    evidence = guard_notes(draft.evidence, limit=6)

    # The conclusion note is where a model most often slips into writing the conclusion itself.
    conclusion = (draft.conclusion_direction or "").strip()
    conclusion_dropped = 0
    if conclusion and is_draft(conclusion):
        conclusion, conclusion_dropped = "", 1

    removed = (
        *for_points.dropped,
        *against_points.dropped,
        *watch_out.dropped,
        *evidence.dropped,
        *((draft.conclusion_direction.strip(),) if conclusion_dropped else ()),
    )
    return GuardedPlan(
        for_points=for_points.kept,
        against_points=against_points.kept,
        evidence=evidence.kept,
        conclusion_direction=conclusion,
        watch_out=watch_out.kept,
        refusal=(draft.refusal or "").strip(),
        dropped=len(removed),
        dropped_notes=removed,
    )


# Wording the student sees when she asks for the answer itself. Held here, not in the prompt, so the refusal
# is the same sentence every time rather than whatever the model felt like saying.
REFUSAL = "I'll plan it with you, but I won't write it — it's your answer, and the marks are for your writing."
