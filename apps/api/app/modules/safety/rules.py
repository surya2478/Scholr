"""Deterministic safety rules and policy (ARCHITECTURE §17).

Rules catch clear signals quickly and without an LLM. Ambiguous signals are marked for
the classifier. The policy table — not an LLM — decides the action.

POLICY_VERSION must change whenever patterns or the policy table change; the parent
reviews this file (see PHASE-1 AC-S4).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Literal

POLICY_VERSION = "safety_v2"  # v2: long numbers in a maths context are not treated as phone numbers

Category = Literal[
    "self_harm",
    "abuse_exploitation",
    "sexual_content",
    "violence",
    "bullying",
    "personal_info",
    "dangerous_activity",
    "hate",
    "academic_integrity",
    "distress",
]


class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: Category
    severity: Severity
    pattern: re.Pattern[str]
    needs_classifier: bool = False
    validator: Callable[[str], bool] | None = None


def _r(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


def _looks_like_phone(match: str) -> bool:
    """Phone numbers have 9+ digits and no maths operators other than separating dashes."""
    digits = sum(ch.isdigit() for ch in match)
    return digits >= 9 and " - " not in match and "." not in match


# Academic context that makes topic words (e.g. "suicide" in Durkheim's study) expected.
_ACADEMIC_CONTEXT = _r(
    r"\b(durkheim|sociolog\w*|statistic\w*|rates?|study|studies|essay|theor\w*|research|"
    r"textbook|exam|question|define|definition|explain|describe|history|historical|biology|"
    r"cells?|media|crime|deviance)\b"
)

# A long digit run in a maths question ("write 1 234 567 890 in standard form") is not a phone number unless the
# message also talks about phones or contact.
_MATHS_CONTEXT = _r(
    r"\b(standard\s+form|divided|divide|multipl\w*|times|calculate|solve|round\w*|estimate|population|"
    r"significant|decimal|fraction|percent\w*|equation|simplify|work\s+out)\b"
)
_PHONE_CONTEXT = _r(r"\b(number|phone|mobile|call|whatsapp|message|text\s+me|contact|dm)\b")

RULES: tuple[Rule, ...] = (
    # --- self-harm: first-person intent (high) ---
    Rule(
        "sh_intent_en",
        "self_harm",
        Severity.HIGH,
        _r(
            r"\b(i\s*(?:'m|am)?\s*(?:want|wanna|going|gonna|plan(?:ning)?|think(?:ing)? (?:about|of))\s*(?:to\s*)?"
            r"(?:kill|hurt|harm|cut|end)\s*(?:myself|my\s*life|it\s*all))\b"
        ),
    ),
    Rule(
        "sh_die_en",
        "self_harm",
        Severity.HIGH,
        _r(
            r"\b(i\s*(?:just\s*)?want\s*to\s*die|i\s*don'?t\s*want\s*to\s*(?:live|be\s*alive|exist)|"
            r"better\s*off\s*(?:dead|without\s*me)|no\s*reason\s*to\s*live|kill\s*myself|end\s*my\s*life)\b"
        ),
    ),
    Rule(
        "sh_hinglish",
        "self_harm",
        Severity.HIGH,
        _r(
            r"\b(mar(?:na)?\s*ja(?:a)?na\s*chah(?:ti|ta)|khud\s*ko\s*(?:khatam|maar|hurt)|"
            r"suicide\s*kar(?:ungi|unga|na))\b"
        ),
    ),
    Rule("sh_arabic", "self_harm", Severity.HIGH, _r(r"(أريد\s*أن\s*أموت|سأقتل\s*نفسي|أؤذي\s*نفسي)")),
    Rule(
        "sh_topic_word",
        "self_harm",
        Severity.MEDIUM,
        _r(r"\b(suicid\w*|self[-\s]?harm\w*)\b|انتحار"),
        needs_classifier=True,
    ),
    # --- abuse / exploitation (high) ---
    Rule(
        "abuse_touch",
        "abuse_exploitation",
        Severity.HIGH,
        _r(r"\b(?:he|she|they|someone|my\s+\w+)\s+(?:touches|touched|hits|hit|beats|beat|hurts|hurt)\s+me\b"),
    ),
    Rule(
        "groom_photos",
        "abuse_exploitation",
        Severity.HIGH,
        _r(r"\b(?:asked|asking|wants?|told)\s+me\s+to\s+send\s+(?:photos?|pics?|pictures?|nudes?|videos?)\b"),
    ),
    Rule(
        "groom_secret",
        "abuse_exploitation",
        Severity.HIGH,
        _r(
            r"\b(?:don'?t|not\s+to|never)\s+tell\s+(?:your|my)\s+(?:parents?|mum|mom|dad|family)\b|"
            r"\bkeep\s+(?:it|this|us)\s+(?:a\s+)?secret\s+from\s+(?:my\s+)?(?:parents?|mum|mom|dad)\b"
        ),
    ),
    # --- violence towards others (high) ---
    Rule(
        "violence_intent",
        "violence",
        Severity.HIGH,
        _r(
            r"\b(?:i\s*(?:'m|am)?\s*(?:want|wanna|going|gonna)\s*to)\s*(?:kill|shoot|stab|hurt|beat\s*up)\s+"
            r"(?:him|her|them|someone|my\s+\w+|everyone)\b"
        ),
    ),
    # --- bullying (medium) ---
    Rule(
        "bullying",
        "bullying",
        Severity.MEDIUM,
        _r(
            r"\b(?:i\s*(?:'m|am)\s*(?:being|getting)\s*bullied|they\s+(?:bully|tease|mock|harass)\s+me|"
            r"everyone\s+(?:hates|laughs\s+at)\s+me)\b"
        ),
    ),
    # --- personal information / meeting strangers (medium) ---
    Rule(
        "pi_phone",
        "personal_info",
        Severity.MEDIUM,
        _r(r"(?<![\d.])\+?\d[\d\s-]{7,}\d(?![\d.])"),
        validator=_looks_like_phone,
    ),
    Rule("pi_address", "personal_info", Severity.MEDIUM, _r(r"\bmy\s+(?:home\s+)?address\s+is\b")),
    Rule(
        "pi_meet",
        "personal_info",
        Severity.MEDIUM,
        _r(
            r"\bmeet(?:ing)?\s+(?:up\s+)?(?:with\s+)?(?:someone|a\s+stranger|him|her|a\s+guy|a\s+girl)\s+"
            r"(?:i|who\s+i)\s+met\s+online\b"
        ),
    ),
    # --- sexual content (medium; classifier decides) ---
    Rule(
        "sexual",
        "sexual_content",
        Severity.MEDIUM,
        _r(r"\b(?:sex(?:ual|ting)?|nudes?|porn\w*)\b"),
        needs_classifier=True,
    ),
    # --- dangerous activity (medium) ---
    Rule(
        "dangerous",
        "dangerous_activity",
        Severity.MEDIUM,
        _r(
            r"\b(?:how\s+(?:do\s+i|to)\s+(?:get|buy|make)\s+(?:drugs|weed|alcohol|vape|a\s+weapon)|"
            r"blackout\s+challenge)\b"
        ),
    ),
    # --- academic integrity (medium) ---
    Rule(
        "integrity",
        "academic_integrity",
        Severity.MEDIUM,
        _r(
            r"\b(?:write|do|finish|complete)\s+(?:my|the)\s+(?:coursework|assignment|individual\s+report|"
            r"homework|essay|project)\s+for\s+me\b"
        ),
    ),
    # --- distress (low, or medium when ambiguous) ---
    Rule(
        "distress_ambiguous",
        "distress",
        Severity.MEDIUM,
        _r(
            r"\b(?:i\s*can'?t\s*(?:do|take)\s*(?:this|it)\s*any\s*more|i\s*give\s*up\s*on\s*everything|"
            r"nobody\s+(?:cares|would\s+notice))\b"
        ),
        needs_classifier=True,
    ),
    Rule(
        "distress_study",
        "distress",
        Severity.LOW,
        _r(
            r"\b(?:so\s+stressed|really\s+stressed|anxious\s+about|panicking|overwhelmed|i\s*hate\s*(?:maths|math|school|studying))\b"
        ),
    ),
)


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    category: Category
    severity: Severity
    needs_classifier: bool


def evaluate_rules(text: str, rules: Sequence[Rule] = RULES) -> list[RuleHit]:
    hits: list[RuleHit] = []
    academic = bool(_ACADEMIC_CONTEXT.search(text))
    maths_not_contact = bool(_MATHS_CONTEXT.search(text)) and not _PHONE_CONTEXT.search(text)
    for rule in rules:
        if rule.rule_id == "pi_phone" and maths_not_contact:
            continue
        matches = [m.group(0) for m in rule.pattern.finditer(text)]
        if rule.validator is not None:
            matches = [m for m in matches if rule.validator(m)]
        if not matches:
            continue
        severity = rule.severity
        if rule.rule_id == "sh_topic_word" and academic:
            severity = Severity.LOW
        hits.append(RuleHit(rule.rule_id, rule.category, severity, rule.needs_classifier))
    return hits


@dataclass(frozen=True)
class ClassifierResult:
    category: Category | None
    severity: Severity
    confidence: float


Action = Literal["allow", "supportive_response", "crisis_response", "integrity_redirect"]


@dataclass(frozen=True)
class SafetyDecision:
    action: Action
    category: Category | None
    severity: Severity
    create_incident: bool
    notify_guardian_now: bool
    policy_version: str
    rule_ids: tuple[str, ...]
    classifier_used: bool
    classifier_failed: bool


def decide(
    hits: Sequence[RuleHit],
    classifier: ClassifierResult | None,
    *,
    classifier_failed: bool = False,
    classifier_min_confidence: float = 0.6,
) -> SafetyDecision:
    """Combine rule hits and classifier output into an action via the policy table."""
    category: Category | None = None
    severity = Severity.NONE

    for hit in hits:
        if hit.severity > severity:
            severity, category = hit.severity, hit.category

    classifier_used = classifier is not None and not classifier_failed
    if classifier_used and classifier is not None:
        if classifier.confidence >= classifier_min_confidence and classifier.severity > severity:
            severity, category = classifier.severity, classifier.category
        needs = [h for h in hits if h.needs_classifier]
        if (
            needs
            and severity == max(h.severity for h in needs)
            and classifier.severity < severity
            and classifier.confidence >= classifier_min_confidence
            and not any(h.severity == Severity.HIGH and not h.needs_classifier for h in hits)
        ):
            # Classifier confidently downgrades an ambiguous-only signal.
            severity = classifier.severity
            category = classifier.category if classifier.severity > Severity.NONE else None
    # classifier failure: keep the rule's own severity (never downgrade on failure).

    if severity >= Severity.HIGH:
        action: Action = "crisis_response"
    elif category == "academic_integrity" and severity >= Severity.MEDIUM:
        action = "integrity_redirect"
    elif severity >= Severity.MEDIUM:
        action = "supportive_response"
    else:
        action = "allow"

    return SafetyDecision(
        action=action,
        category=category,
        severity=severity,
        create_incident=severity >= Severity.MEDIUM and category != "academic_integrity",
        notify_guardian_now=severity >= Severity.HIGH,
        policy_version=POLICY_VERSION,
        rule_ids=tuple(h.rule_id for h in hits),
        classifier_used=classifier_used,
        classifier_failed=classifier_failed,
    )
