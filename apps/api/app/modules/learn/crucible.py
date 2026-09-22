"""The Crucible: perspectives on a real Sociology essay question, from her own coursebook (review of 22 Sep 2026).

Replaced a hand-written set whose sociologists, studies and "Level 4" descriptors had no source, and whose "marking"
counted keywords. Now:

- the question is a real past-paper essay question from the bank (the highest-mark one on the topic);
- every perspective cites the coursebook excerpts it rests on, may name a sociologist or study only if a cited
  excerpt does, and may not copy the book (the lesson guard's own rules: ``lessons.unsupported_names``, copy runs);
- it ends with questions for her to weigh — never an answer or a conclusion (AC-R5);
- a person approves it before she sees it, and her answer is written and marked the normal way, not by keywords.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.llm.text_repair import repair_json_escapes
from app.modules.learn import lessons
from app.tools import text_overlap

GUARD_VERSION = "crucible_guard_v2"
# Schools of thought, not people: a perspective's own name is not a name that needs a citation ("New Right").
PERSPECTIVE_TERMS = (
    "Functionalist Functionalists Functionalism Marxist Marxists Marxism Feminist Feminists Feminism Interactionist "
    "Interactionists Interactionism New Right Postmodernist Postmodernists Postmodernism Pluralist Pluralists "
    "Pluralism Interpretivist Interpretivists Positivist Positivists Liberal Radical Neo-Marxist Neo-Marxists"
)
MIN_PERSPECTIVES = 2
MAX_PERSPECTIVES = 4
MAX_QUESTIONS = 3
MAX_QUESTION_WORDS = 30


class DraftPerspective(BaseModel):
    model_config = ConfigDict(extra="ignore")
    perspective: str
    sociologist: str = ""
    argument: str
    key_concept: str = ""
    evidence: str = ""
    sources: list[int] = Field(default_factory=list)


class CrucibleDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    perspectives: list[DraftPerspective] = Field(default_factory=list)
    questions_to_weigh: list[str] = Field(default_factory=list)


def guard(draft: CrucibleDraft, excerpts: Sequence[lessons.Excerpt]) -> tuple[dict | None, dict]:
    """(content, report). Content is None unless at least two different perspectives survive the checks."""
    fix = repair_json_escapes
    report = {
        "kept": 0,
        "dropped_uncited": 0,
        "dropped_named": 0,
        "dropped_copied": 0,
        "evidence_dropped": 0,
        "dropped_questions": 0,
    }
    kept: list[dict] = []
    for p in draft.perspectives:
        numbers = [n for n in dict.fromkeys(p.sources) if 0 < n <= len(excerpts)]
        if not numbers:
            report["dropped_uncited"] += 1
            continue
        cited = "\n".join(excerpts[n - 1].text for n in numbers)
        fields = {k: fix(getattr(p, k)).strip() for k in ("sociologist", "argument", "key_concept", "evidence")}
        # Each field on its own, so the start of one is not read as the middle of a sentence in another.
        named = cited + "\n" + PERSPECTIVE_TERMS
        if any(lessons.unsupported_names(v, named) for v in fields.values() if v) or (
            fields["sociologist"] and fields["sociologist"].lower() not in cited.lower()
        ):
            report["dropped_named"] += 1
            continue
        ngrams = text_overlap.source_ngrams(cited, lessons.COPY_RUN)
        if text_overlap.copies_source(fields["argument"], ngrams, lessons.COPY_RUN):
            report["dropped_copied"] += 1
            continue
        if fields["evidence"] and text_overlap.copies_source(fields["evidence"], ngrams, lessons.COPY_RUN):
            fields["evidence"] = ""  # a copied example goes; the perspective, in her own words, stays
            report["evidence_dropped"] += 1
        kept.append(
            {
                "perspective": fix(p.perspective).strip(),
                **fields,
                # One entry per page: two passages from the same page are one reference.
                "sources": [
                    {"title": title, "page": page}
                    for title, page in dict.fromkeys(
                        (excerpts[n - 1].source_title, excerpts[n - 1].page) for n in numbers
                    )
                ],
            }
        )
    kept = kept[:MAX_PERSPECTIVES]
    report["kept"] = len(kept)
    everything = "\n".join(e.text for e in excerpts)
    questions = []
    for q in draft.questions_to_weigh:
        q = " ".join(fix(q).split())
        # A question to weigh, not an answer in disguise: it asks, it is short, and it names no one unsupported.
        if (
            q.endswith("?")
            and len(q.split()) <= MAX_QUESTION_WORDS
            and not lessons.unsupported_names(q, everything + "\n" + PERSPECTIVE_TERMS)
        ):
            questions.append(q)
        else:
            report["dropped_questions"] += 1
    if len({p["perspective"].lower() for p in kept}) < MIN_PERSPECTIVES:
        return None, report
    return {"perspectives": kept, "questions": questions[:MAX_QUESTIONS], "guard_version": GUARD_VERSION}, report
