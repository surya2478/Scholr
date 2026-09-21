"""Master Router rules (ARCHITECTURE §7), pure: intent from wording, subject/objective from a keyword index restricted
to the student's enrollments. No LLM here — the classifier is only consulted when these rules are not confident."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.modules.safety.rules import evaluate_rules

INTENTS = ("explain", "practice", "help_on_attempt", "check_answer", "plan", "progress", "off_topic", "wellbeing")
WELLBEING_CATEGORIES = frozenset({"self_harm", "distress", "abuse_exploitation", "bullying"})
_INTENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "check_answer",
        re.compile(r"\b(check|mark)\b.*\b(answer|working|this)\b|\bis (this|my answer) (right|correct)\b", re.I),
    ),
    (
        "help_on_attempt",
        re.compile(r"\b(stuck|hint|i (?:don'?t|do not) (?:get|understand)|help me with (?:this|question))\b", re.I),
    ),
    ("practice", re.compile(r"\b(practi[cs]e|quiz me|test me|give me (?:a |some )?questions?|more questions)\b", re.I)),
    ("plan", re.compile(r"\b(my plan|today'?s plan|what should i (?:do|study)|schedule|timetable)\b", re.I)),
    ("progress", re.compile(r"\b(my progress|how am i doing|my (?:level|mastery)|my weak|my strong)\b", re.I)),
)
_STOP_WORDS = (
    "about above after again also another because been before being between both could does doing during each "
    "explain from have having help into just like more most much need other over please question questions "
    "should some such than that their them then there these they this those through topic under very want "
    "what when where which while with would your how why who can the and for are you not work works thing"
)
_STOP = frozenset(_STOP_WORDS.split())
_WORD = re.compile(r"[a-z][a-z'-]{2,}")
MIN_RULE_SCORE = 2.0
MIN_RULE_MARGIN = 1.0


@dataclass(frozen=True)
class IndexEntry:
    subject_id: UUID
    subject_name: str
    subject_aliases: frozenset[str]
    objective_id: UUID
    objective_code: str
    words: frozenset[str]
    label: str


@dataclass(frozen=True)
class Candidate:
    entry: IndexEntry
    score: float


@dataclass(frozen=True)
class RuleMatch:
    confident: bool  # the subject is clear
    candidates: list[Candidate]
    objective_confident: bool = False  # the top objective clearly beats the runner-up


def words(text: str) -> set[str]:
    out = set()
    for w in _WORD.findall(text.lower()):
        w = w.strip("'-")
        if len(w) > 2 and w not in _STOP:
            out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


def subject_aliases(name: str, code: str) -> frozenset[str]:
    parts = code.lower().split("-")  # codes are "<qualification>-<subject>"; the qualification is not an alias
    base = {name.lower(), *(parts[1:] or parts)}
    return frozenset(base | {a[:-1] for a in base if a.endswith("s")})


def intent_for(text: str) -> str:
    if any(hit.category in WELLBEING_CATEGORIES for hit in evaluate_rules(text)):
        return "wellbeing"
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return "explain"


def match(text: str, index: Sequence[IndexEntry]) -> RuleMatch:
    message = words(text)
    lowered = text.lower()
    scored: list[Candidate] = []
    for entry in index:
        overlap = len(message & entry.words)
        bonus = 1.0 if any(re.search(rf"\b{re.escape(a)}\b", lowered) for a in entry.subject_aliases) else 0.0
        if overlap or bonus:
            scored.append(Candidate(entry, overlap + bonus))
    scored.sort(key=lambda c: (-c.score, c.entry.objective_code))
    if not scored:
        return RuleMatch(False, [])
    best = scored[0]
    best_by_subject: dict[UUID, float] = defaultdict(float)
    for c in scored:
        best_by_subject[c.entry.subject_id] = max(best_by_subject[c.entry.subject_id], c.score)
    other_subjects = [v for sid, v in best_by_subject.items() if sid != best.entry.subject_id]
    runner_up = scored[1].score if len(scored) > 1 else 0.0
    confident = best.score >= MIN_RULE_SCORE and (
        not other_subjects or best.score - max(other_subjects) >= MIN_RULE_MARGIN
    )
    return RuleMatch(confident, scored[:5], objective_confident=confident and best.score - runner_up >= MIN_RULE_MARGIN)
