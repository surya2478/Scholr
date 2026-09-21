"""Past-paper question bank: extract items from official question papers + mark schemes.

The LLM structures what is printed; deterministic checks decide whether an item is verified:
- refs are well-formed and unique, and no page failed extraction,
- marks add up to the paper total (where every question is compulsory),
- numeric answers from the mark scheme agree with the exact value (SymPy, ranges ignored),
- every number in the extracted answer appears in that question's mark-scheme row (when the row can be found).

When the mark scheme's question table can be parsed deterministically (app.modules.assessment.mark_scheme), the
parsed answer, marks and marking guidance are authoritative: the LLM supplies only question text, answer type, exact
value and objective codes (prompt v2), and the checks become: every extracted ref is a table row and vice versa, the
table's marks add up to the printed total, and the extractor's exact value agrees with the official answer.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.gateway import CallContext, ImageInput, LLMError, LLMGateway
from app.llm.text_repair import repair_json_escapes
from app.modules.assessment.mark_scheme import MarkSchemeRow, MarkSchemeTable
from app.modules.assessment.mark_scheme import numbers as table_numbers
from app.modules.assessment.mark_scheme import plain as plain_numbers
from app.modules.assessment.models import QuestionItem
from app.tools.math_sympy import MathParseError, NumericSpec, check_numeric, equivalent, parse_math

EXTRACT_PROMPT = "past_paper_extract"
PROMPT_V1 = "v1"  # items incl. answer and mark scheme, from the whole mark-scheme text
PROMPT_V2 = "v2"  # question text only; answers from the parsed mark-scheme table
EXTRACTOR_ROLE = "paper_extractor"
LOOP_RETRY_TEMPERATURE = 0.4

AnswerType = Literal[
    "numeric",
    "expression",
    "coordinates",
    "set_of_values",
    "text_short",
    "explanation",
    "drawing",
    "extended_response",
]


class ExtractedItem(BaseModel):
    ref: str
    context: str | None = None
    stem: str
    marks: int = Field(ge=1, le=30)
    command_word: str | None = None
    has_diagram: bool = False
    answer_type: AnswerType
    answer: str
    mark_scheme: str
    exact_value: str | None = None
    accept_ranges: list[tuple[str, str]] = Field(default_factory=list)
    accuracy: Literal["sf3", "dp1_angle", "exact"] = "sf3"
    objective_codes: list[str] = Field(default_factory=list)


class ExtractedPage(BaseModel):
    items: list[ExtractedItem]


class ExtractedQuestion(BaseModel):
    """Prompt v2 output: question text only. Answer, marks and guidance come from the parsed mark-scheme row."""

    ref: str
    context: str | None = None
    stem: str
    command_word: str | None = None
    has_diagram: bool = False
    answer_type: AnswerType
    exact_value: str | None = None
    accuracy: Literal["sf3", "dp1_angle", "exact"] = "sf3"
    objective_codes: list[str] = Field(default_factory=list)


class ExtractedQuestionPage(BaseModel):
    items: list[ExtractedQuestion]


def item_from_row(question: ExtractedQuestion, row: MarkSchemeRow) -> ExtractedItem:
    """Question text from the extractor; answer, marks, guidance and ranges from the official mark-scheme row."""
    return ExtractedItem(
        ref=row.ref,
        context=question.context,
        stem=question.stem,
        marks=max(1, min(30, row.marks or 1)),  # unreadable marks are flagged by check_paper_against_table
        command_word=question.command_word,
        has_diagram=question.has_diagram,
        answer_type=question.answer_type,
        answer=row.answer,
        mark_scheme=row.guidance,
        exact_value=question.exact_value,
        accept_ranges=list(row.accept_ranges),
        accuracy=question.accuracy,
        objective_codes=question.objective_codes,
    )


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------

# 7, 7(a), 7(b)(ii), and the occasional fourth level 2(a)(vi)(a).
_REF = re.compile(r"^(\d{1,2})((?:\([a-z]\))?(?:\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)(?:\([a-z]\))?)?)$")
_TOTAL = re.compile(r"total mark for this paper is\s+(\d+)", re.IGNORECASE)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


def normalise_ref(ref: str) -> str | None:
    compact = re.sub(r"\s+", "", ref).lower().removeprefix("q")
    return compact if _REF.match(compact) else None


def parent_of(ref: str) -> str:
    m = _REF.match(ref)
    return m.group(1) if m else ref


def parse_total_marks(cover_text: str) -> int | None:
    m = _TOTAL.search(cover_text)
    return int(m.group(1)) if m else None


def first_numeric_answer(answer: str) -> str | None:
    head = re.split(r"\bor\b|;|,(?!\d{3})", answer, maxsplit=1)[0]
    m = _NUMBER.search(head.replace("−", "-"))
    return m.group(0) if m else None


def numeric_issue(item: ExtractedItem) -> str | None:
    """Return an issue code if a numeric answer disagrees with its exact value, else None."""
    if item.answer_type != "numeric" or not item.exact_value:
        return None
    candidate = first_numeric_answer(item.answer)
    if candidate is None:
        return "answer_not_numeric"
    accuracy, places = {"sf3": ("sf", 3), "dp1_angle": ("dp", 1), "exact": ("exact", 3)}[item.accuracy]
    try:
        # Ranges are deliberately not used here: a mark-scheme range accepting the printed answer says nothing about
        # whether exact_value is right (an angle's exact value in radians passed this way before).
        spec = NumericSpec(exact=item.exact_value, accuracy=accuracy, places=places)  # type: ignore[arg-type]
        verdict = check_numeric(candidate, spec)
    except (ValueError, MathParseError):
        return "exact_value_unparseable"
    return None if verdict.status == "correct" else f"answer_exact_mismatch:{verdict.status}"


@dataclass
class PaperCheck:
    issues: list[str] = field(default_factory=list)  # block every item on the paper
    item_issues: dict[str, list[str]] = field(default_factory=dict)
    advisories: list[str] = field(default_factory=list)  # recorded, but only the items concerned stay unverified

    @property
    def ok(self) -> bool:
        return not self.issues


# A question-table row in a Cambridge mark scheme's text layer starts near the left margin with the part ref.
# Answer-column content (e.g. the numerator of a stacked fraction) is indented further, so it is not a new row.
_MS_TABLE_HEADER = re.compile(r"Question\s+Answer\s+Marks")
_MS_ROW = re.compile(
    r"^[ \t]{0,8}(\d{1,2}(?:\s?\([a-z]\))?(?:\s?\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\))?)(?=[ \t]{2,}|[ \t]*$)",
    re.MULTILINE,
)
_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")


def mark_scheme_rows(mark_scheme_text: str) -> dict[str, str]:
    """Split a mark-scheme question table (text layer) into row text keyed by normalised ref. {} if no table."""
    header = _MS_TABLE_HEADER.search(mark_scheme_text)
    if header is None:
        return {}
    body = mark_scheme_text[header.end() :]
    rows: dict[str, str] = {}
    last_parent = 0
    starts: list[tuple[str, int, int]] = []
    for match in _MS_ROW.finditer(body):
        ref = normalise_ref(match.group(1))
        if ref is None:
            continue
        parent = int(parent_of(ref))
        if parent < last_parent or (parent == last_parent and ref == str(parent)):
            continue  # an indented number inside the previous row, not a new question
        last_parent = parent
        starts.append((ref, match.start(), match.end()))
    for i, (ref, _, end) in enumerate(starts):
        stop = starts[i + 1][1] if i + 1 < len(starts) else len(body)
        rows[ref] = rows.get(ref, "") + " " + body[end:stop]
    return rows


def _numbers(text: str) -> set[str]:
    cleaned = text.replace(", ", " ").replace(",", "")
    return {format(Decimal(n).normalize(), "f") for n in _NUMBER_TOKEN.findall(cleaned)}


def answer_located(answer: str, ref: str, rows: dict[str, str]) -> bool | None:
    """Every number in the extracted answer appears in that question's mark-scheme row.

    None when it cannot be checked: no numbers in the answer, no parseable table, or no row found for the ref
    (layouts vary, so a missing row is not evidence of a wrong answer). False when the row exists but a number is
    absent — e.g. a value copied from the neighbouring part.
    """
    numbers = _numbers(answer)
    if not numbers or not rows:
        return None
    row = rows.get(ref) or " ".join(text for key, text in rows.items() if key.startswith(ref + "("))
    if not row:
        return None
    return numbers <= _numbers(row)


def check_paper(
    items: Sequence[ExtractedItem], *, expected_total: int | None, mark_scheme_text: str | None = None
) -> PaperCheck:
    check = PaperCheck()
    seen: set[str] = set()
    rows = mark_scheme_rows(mark_scheme_text) if mark_scheme_text else {}
    for item in items:
        ref = normalise_ref(item.ref)
        if ref is None:
            check.issues.append(f"bad_ref:{item.ref}")
            continue
        if ref in seen:
            check.issues.append(f"duplicate_ref:{ref}")
        seen.add(ref)
        problem = numeric_issue(item)
        if problem:
            check.item_issues.setdefault(ref, []).append(problem)
        if answer_located(item.answer, ref, rows) is False:
            check.item_issues.setdefault(ref, []).append("answer_not_in_mark_scheme")
    if expected_total is not None:
        total = sum(i.marks for i in items)
        if total != expected_total:
            check.issues.append(f"marks_total:{total}!={expected_total}")
    return check


# Marking shorthand that appears in official answers without making them prose.
_SHORTHAND_WORDS = {"cao", "isw", "nfww", "soi", "dep", "www", "final", "answer", "and", "only", "ruled", "oe", "or"}


def answer_type_issue(answer_type: str, answer: str) -> str | None:
    """A prose answer type for an official answer with no prose (only values, symbols and marking shorthand)."""
    if answer_type not in ("explanation", "extended_response") or not answer.strip():
        return None
    words = [w for w in re.findall(r"[A-Za-z]{3,}", answer) if w.lower() not in _SHORTHAND_WORDS]
    return None if words else "answer_type_inconsistent"


def check_paper_against_table(
    items: Sequence[ExtractedItem],
    table: MarkSchemeTable,
    *,
    expected_total: int | None,
    unmatched_refs: Sequence[str] = (),
) -> PaperCheck:
    """Checks for items whose answer, marks and guidance were taken from a parsed mark-scheme table.

    Paper level (blocking): refs are well formed and unique.
    Advisories (recorded, not blocking): extractor refs with no table row, rows that were not extracted, and totals that
    differ from the printed total. Answers and marks come from each item's own row, so one unreadable row or a
    mis-split part does not make the other items unreliable; an item without its row stays unverified.
    Item level: the row has an answer and readable marks equal to the item's, and the exact value agrees with it.
    """
    check = PaperCheck()
    rows = table.by_ref()
    seen: set[str] = set()
    for raw in unmatched_refs:
        check.advisories.append(f"ref_not_in_mark_scheme:{raw}")
        check.item_issues.setdefault(normalise_ref(raw) or raw, []).append("ref_not_in_mark_scheme")
    for item in items:
        ref = normalise_ref(item.ref)
        if ref is None:
            check.issues.append(f"bad_ref:{item.ref}")
            continue
        if ref in seen:
            check.issues.append(f"duplicate_ref:{ref}")
        seen.add(ref)
        row = rows.get(ref)
        if row is None:
            check.advisories.append(f"ref_not_in_mark_scheme:{ref}")
            check.item_issues.setdefault(ref, []).append("ref_not_in_mark_scheme")
            continue
        issues: list[str] = []
        if row.marks is None:
            issues.append("mark_scheme_marks_unreadable")
        elif item.marks != row.marks:
            issues.append("marks_disagree_mark_scheme")
        if not row.answer.strip():
            issues.append("mark_scheme_answer_empty")
        elif problem := answer_type_issue(item.answer_type, row.answer):
            issues.append(problem)
        if "diagram" in row.notation:
            issues.append("mark_scheme_answer_has_diagram")  # the printed text is not the whole answer
        if problem := numeric_issue(item.model_copy(update={"answer": plain_numbers(item.answer)})):
            issues.append(problem)
        if issues:
            check.item_issues.setdefault(ref, []).extend(issues)
    check.advisories.extend(f"mark_scheme_ref_not_extracted:{ref}" for ref in rows if ref not in seen)
    if expected_total is not None:
        if table.total_marks != expected_total:
            check.advisories.append(f"mark_scheme_total:{table.total_marks}!={expected_total}")
        total = sum(i.marks for i in items)
        if total != expected_total:
            check.advisories.append(f"marks_total:{total}!={expected_total}")
    return check


def table_disagreements(ref: str, marks: int, answer: str, rows: dict[str, MarkSchemeRow]) -> list[str]:
    """Issues for a stored item compared with its parsed mark-scheme row (re-check)."""
    row = rows.get(ref)
    if row is None:
        return ["ref_not_in_mark_scheme"]
    issues: list[str] = []
    if row.marks is not None and row.marks != marks:
        issues.append("marks_disagree_mark_scheme")
    if not table_numbers(answer) <= table_numbers(row.answer):
        issues.append("answer_disagree_mark_scheme")
    return issues


ObjectiveMap = dict[str, tuple[UUID, UUID]]  # objective code -> (objective id, topic id)


def item_status(
    item: ExtractedItem, check: PaperCheck, objective_map: ObjectiveMap
) -> tuple[str, list[str], list[tuple[UUID, UUID]]]:
    """(verification status, item issues, known objectives) — an item is verified only if every check passes."""
    issues = list(check.item_issues.get(item.ref, []))
    unknown = [c for c in item.objective_codes if c not in objective_map]
    if unknown:
        issues.append("unknown_objectives:" + ",".join(unknown))
    known = [objective_map[c] for c in item.objective_codes if c in objective_map]
    return ("verified" if check.ok and not issues else "unverified"), issues, known


_REPAIRABLE_FIELDS = ("context", "stem", "answer", "mark_scheme", "command_word")


def repair_item[M: BaseModel](item: M) -> M:
    updates = {}
    for name in _REPAIRABLE_FIELDS:
        value = getattr(item, name, None)
        if isinstance(value, str) and (fixed := repair_json_escapes(value)) != value:
            updates[name] = fixed
    return item.model_copy(update=updates) if updates else item


@dataclass(frozen=True)
class ReferenceItem:
    """An item already in the bank, used to screen another extraction model."""

    ref: str
    marks: int
    answer_type: str
    answer: str
    exact: str | None


@dataclass(frozen=True)
class ExtractionComparison:
    reference_items: int
    candidate_items: int
    matched: int
    missing_refs: list[str]
    extra_refs: list[str]
    marks_agree: int
    type_agree: int
    answer_agree: int
    exact_compared: int
    exact_agree: int
    # Items the candidate would mark verified that disagree with the bank on marks, type, answer or exact value:
    # the safety number — anything here would reach students with a wrong answer spec.
    verified_disagreements: list[str]
    differences: dict[str, list[str]]  # matched ref -> names of the fields that disagree

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalise_answer(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("−", "-")).lower().rstrip(".")


def _same_value(a: str, b: str) -> bool:
    try:
        return equivalent(parse_math(a, rational=True), parse_math(b, rational=True))
    except (MathParseError, TypeError, ValueError):
        return False


def compare_extractions(
    reference: Sequence[ReferenceItem], candidate: Sequence[ExtractedItem], *, verified_refs: Collection[str] = ()
) -> ExtractionComparison:
    ref_by = {r.ref: r for r in reference}
    cand_by = {normalise_ref(c.ref) or c.ref: c for c in candidate}
    matched = [ref for ref in ref_by if ref in cand_by]
    marks = types = answers = exact_compared = exact_agree = 0
    disagreements: list[str] = []
    differences: dict[str, list[str]] = {}
    for ref in matched:
        r, c = ref_by[ref], cand_by[ref]
        marks_ok = r.marks == c.marks
        type_ok = r.answer_type == c.answer_type
        first_r, first_c = first_numeric_answer(r.answer), first_numeric_answer(c.answer)
        answer_ok = _normalise_answer(r.answer) == _normalise_answer(c.answer) or (
            first_r is not None and first_r == first_c
        )
        exact_ok = True
        if r.exact and c.exact_value:
            exact_compared += 1
            exact_ok = _same_value(r.exact, c.exact_value)
            exact_agree += exact_ok
        marks, types, answers = marks + marks_ok, types + type_ok, answers + answer_ok
        fields = [
            name
            for name, ok in (("marks", marks_ok), ("type", type_ok), ("answer", answer_ok), ("exact", exact_ok))
            if not ok
        ]
        if fields:
            differences[ref] = fields
            if ref in verified_refs:
                disagreements.append(ref)
    return ExtractionComparison(
        reference_items=len(ref_by),
        candidate_items=len(cand_by),
        matched=len(matched),
        missing_refs=sorted(set(ref_by) - set(cand_by)),
        extra_refs=sorted(set(cand_by) - set(ref_by)),
        marks_agree=marks,
        type_agree=types,
        answer_agree=answers,
        exact_compared=exact_compared,
        exact_agree=exact_agree,
        verified_disagreements=disagreements,
        differences=differences,
    )


def merge_pages(pages: Sequence[tuple[int, Sequence[ExtractedItem]]]) -> list[tuple[ExtractedItem, list[int]]]:
    """Merge per-page extractions; a part seen on two pages keeps the first extraction and both page numbers."""
    merged: dict[str, tuple[ExtractedItem, list[int]]] = {}
    order: list[str] = []
    for page_number, items in pages:
        for item in items:
            ref = normalise_ref(item.ref) or item.ref
            if ref in merged:
                merged[ref][1].append(page_number)
                continue
            merged[ref] = (item.model_copy(update={"ref": ref}), [page_number])
            order.append(ref)
    return [merged[r] for r in order]


# ---------------------------------------------------------------------------
# Extraction and persistence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperInput:
    syllabus_code: str  # "0580"
    component: str  # "21"
    series: str  # "MJ24"
    label: str
    subject_notes: str
    page_texts: dict[int, str]  # page number -> text
    page_images: dict[int, bytes]
    mark_scheme_text: str
    objectives_prompt: str
    expected_total: int | None


PageItems = tuple[int, list[ExtractedItem]]


@dataclass(frozen=True)
class PaperExtraction:
    pages: list[PageItems]
    model: str
    prompt_version: str
    cost_usd: float
    failed_pages: dict[int, str]  # page number -> error code; any failure keeps the whole paper unverified
    unmatched_refs: list[str] = field(default_factory=list)  # v2: extractor refs with no mark-scheme row (dropped)


def _pending_refs(table: MarkSchemeTable, extracted: Collection[str], limit: int = 20) -> str:
    pending = [row for row in table.rows if row.ref not in extracted][:limit]
    return ", ".join(f"{row.ref} [{row.marks if row.marks is not None else '?'}]" for row in pending) or "none"


def extract_paper(
    gateway: LLMGateway,
    ctx: CallContext,
    paper: PaperInput,
    *,
    role: str = EXTRACTOR_ROLE,
    models: Sequence[str] | None = None,
    table: MarkSchemeTable | None = None,
) -> PaperExtraction:
    """Run page-by-page extraction. A failed page is recorded, not fatal (except quota / configuration).

    With a parsed mark-scheme table, prompt v2 extracts question text only and each item takes its answer, marks and
    guidance from the table row for its ref; refs with no row are dropped and reported in unmatched_refs.
    Without one, prompt v1 extracts answers and mark schemes from the mark-scheme text.
    """
    results: list[tuple[int, list[ExtractedItem]]] = []
    previous: list[str] = []
    failed: dict[int, str] = {}
    unmatched: list[str] = []
    rows = table.by_ref() if table is not None else {}
    model = prompt_version = ""
    cost = 0.0
    for number in sorted(paper.page_texts):
        text = paper.page_texts[number]
        if number == 1 or "[" not in text:  # cover page / blank page: no mark allocations
            continue
        variables = {
            "paper_label": paper.label,
            "subject_notes": paper.subject_notes,
            "objectives": paper.objectives_prompt,
            "previous_refs": ", ".join(previous[-15:]) or "none",
            "page_number": str(number),
            "page_text": text,
        }
        schema: type[BaseModel]
        if table is None:
            variables["mark_scheme"] = paper.mark_scheme_text
            schema, version = ExtractedPage, PROMPT_V1
        else:
            variables["mark_scheme_refs"] = _pending_refs(table, set(previous))
            schema, version = ExtractedQuestionPage, PROMPT_V2
        images = [ImageInput(paper.page_images[number], "image/png")] if number in paper.page_images else []
        result = None
        # Low-cost models can fall into a repetition loop at temperature 0 (e.g. a run of dashes until the output
        # is cut off). A page whose output is invalid gets one fresh attempt at a slightly higher temperature.
        for temperature in (None, LOOP_RETRY_TEMPERATURE):
            try:
                result = gateway.structured(
                    role,
                    EXTRACT_PROMPT,
                    variables,
                    schema,
                    ctx,
                    images=images,
                    models=models,
                    temperature=temperature,
                    prompt_version=version,
                )
            except LLMError as exc:
                if exc.code in ("quota_exceeded", "not_configured"):
                    raise
                failed[number] = exc.code
                if exc.code != "invalid_output":
                    break
                continue
            failed.pop(number, None)
            break
        if result is None:
            continue
        model, prompt_version = result.model, result.prompt_version
        cost += result.cost_usd or 0.0
        items: list[ExtractedItem] = []
        for extracted in result.value.items:  # type: ignore[attr-defined]
            extracted = repair_item(extracted)
            if table is None:
                items.append(extracted)
                continue
            row = rows.get(normalise_ref(extracted.ref) or "")
            if row is None:
                unmatched.append(extracted.ref)
                continue
            items.append(item_from_row(extracted, row))
        results.append((number, items))
        previous.extend(normalise_ref(i.ref) or i.ref for i in items)
    return PaperExtraction(results, model, prompt_version, cost, failed, unmatched)


_ACCURACIES = ("sf3", "dp1_angle", "exact")


def recheck_transition(status: str, reserved: bool, issues: Sequence[str], meta: dict[str, object]) -> str | None:
    """New verification status after a deterministic re-check, or None to leave the item as it is.

    Verified items with issues are demoted. An item is restored only if a previous re-check demoted it and its
    original extraction had no item or paper issues. Study-reserved items are never changed.
    """
    if reserved:
        return None
    if issues:
        return "unverified" if status == "verified" else None
    if (
        status == "unverified"
        and meta.get("recheck_issues")
        and not meta.get("item_issues")
        and not meta.get("paper_issues")
    ):
        return "verified"
    return None


def recheck_bank_items(
    s: Session,
    *,
    prefix: str,
    mark_scheme_text: str,
    table: MarkSchemeTable | None = None,
    apply: bool = True,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Re-run the deterministic item checks on stored items (no LLM calls).

    With a parsed mark-scheme table, stored marks and answer numbers are compared with the official row for the ref;
    otherwise every answer number must appear in the text-layer row. apply=False reports without changing any row.
    Returns (demoted, restored): ref -> issues found now / issues that caused the earlier demotion.
    """
    rows = mark_scheme_rows(mark_scheme_text) if table is None else {}
    table_rows = table.by_ref() if table is not None else {}
    demoted: dict[str, list[str]] = {}
    restored: dict[str, list[str]] = {}
    for row in s.scalars(
        select(QuestionItem).where(QuestionItem.source_ref.like(prefix + "%"), QuestionItem.origin == "past_paper")
    ):
        spec = row.answer_spec or {}
        ref = (row.source_ref or "").removeprefix(prefix)
        issues: list[str] = []
        if spec.get("type") == "numeric" and spec.get("exact"):
            probe = ExtractedItem(
                ref=ref,
                stem=row.stem or "-",
                marks=max(1, min(30, row.marks)),
                answer_type="numeric",
                answer=str(spec.get("answer", "")),
                mark_scheme="-",
                exact_value=str(spec["exact"]),
                accuracy=spec.get("accuracy") if spec.get("accuracy") in _ACCURACIES else "sf3",
                accept_ranges=[tuple(r) for r in spec.get("accept_ranges") or [] if len(r) == 2],
            )
            if problem := numeric_issue(probe):
                issues.append(problem)
        answer = str(spec.get("answer", ""))
        if table is not None:
            issues.extend(table_disagreements(ref, row.marks, answer, table_rows))
        elif answer_located(answer, ref, rows) is False:
            issues.append("answer_not_in_mark_scheme")
        meta = dict(row.meta or {})
        transition = recheck_transition(row.verification_status, row.reserved_for_study, issues, meta)
        if transition == "unverified":
            demoted[ref] = issues
            if apply:
                row.verification_status = "unverified"
                row.verified_by = None
                row.meta = {**meta, "recheck_issues": issues}
        elif transition == "verified":
            restored[ref] = list(meta.get("recheck_issues") or [])
            if apply:
                row.verification_status = "verified"
                row.verified_by = "recheck_v2" if table is not None else "recheck_v1"
                row.meta = {**meta, "recheck_issues": []}
    if apply:
        s.flush()
    return demoted, restored


def _without_nul(item: ExtractedItem) -> ExtractedItem:
    fields = ("stem", "context", "answer", "mark_scheme", "command_word", "exact_value")
    updates = {f: getattr(item, f).replace("\x00", "") for f in fields if isinstance(getattr(item, f), str)}
    return item.model_copy(update=updates)


def save_items(
    s: Session,
    *,
    tenant_id: UUID,
    subject_id: UUID,
    source_id: UUID,
    paper: PaperInput,
    merged: Sequence[tuple[ExtractedItem, list[int]]],
    check: PaperCheck,
    objective_map: ObjectiveMap,
    calculator_allowed: bool | None,
    model: str,
    prompt_version: str,
    answers_from_table: bool = False,
) -> tuple[int, int]:
    """Upsert items. Returns (saved, verified). answers_from_table: answers/marks came from the parsed mark scheme."""
    saved = verified = 0
    for item, pages in merged:
        item = _without_nul(item)  # symbol-font glyphs can extract as NUL, which PostgreSQL text rejects
        ref = item.ref
        source_ref = f"{paper.syllabus_code}/{paper.component}/{paper.series}/Q{ref}"
        status, issues, known = item_status(item, check, objective_map)
        values = {
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "origin": "past_paper",
            "source_id": source_id,
            "parent_ref": f"{paper.syllabus_code}/{paper.component}/{paper.series}/Q{parent_of(ref)}",
            "stem": item.stem,
            "context": item.context,
            "marks": item.marks,
            "command_word": item.command_word,
            "objective_ids": list(dict.fromkeys(o for o, _ in known)),
            "topic_ids": list(dict.fromkeys(t for _, t in known)),
            "calculator_allowed": calculator_allowed,
            "has_diagram": item.has_diagram,
            "answer_spec": {
                "type": item.answer_type,
                "answer": item.answer,
                "exact": item.exact_value,
                "accuracy": item.accuracy,
                "accept_ranges": [list(r) for r in item.accept_ranges],
            },
            "mark_scheme": {
                "text": item.mark_scheme,
                "source": "official_mark_scheme",
                "parsed_table": answers_from_table,
            },
            "verification_status": status,
            "verified_by": (
                None
                if status != "verified"
                else "extraction_checks_v2"
                if answers_from_table
                else "extraction_checks_v1"
            ),
            "source_pages": pages,
            "meta": {
                "extractor_model": model,
                "prompt": f"{EXTRACT_PROMPT}/{prompt_version}",
                "answer_source": "mark_scheme_table" if answers_from_table else "extractor",
                "item_issues": issues,
                "paper_issues": check.issues,
                "paper_advisories": check.advisories,
            },
        }
        row = s.scalar(select(QuestionItem).where(QuestionItem.source_ref == source_ref))
        if row is None:
            s.add(QuestionItem(source_ref=source_ref, **values))
        elif not row.reserved_for_study:
            for key, value in values.items():
                setattr(row, key, value)
        saved += 1
        verified += status == "verified"
    s.flush()
    return saved, verified
