"""essay_levels pipeline (ARCHITECTURE §12.2): deterministic text checks → two independent markers from different
model families → agreement check against config.max_disagreement → confidence → status.

Nothing is final while the subject's evaluator is not calibrated (AC-E5): the student still gets provisional feedback,
and mastery is not updated until a person reviews the mark.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.llm.gateway import CallContext, LLMError, LLMGateway
from app.llm.text_repair import repair_json_escapes
from app.modules.evaluation.structured_math import DiagnosedMistake, fingerprint
from app.tools.text_checks import TextChecks, check_answer

PIPELINE = "essay_levels"
PIPELINE_VERSION = "essay_levels_v1"
PROMPT = "essay_mark"
LEVELS_FROM_MARKS = 8  # items worth this many marks or more are level-marked
SINGLE_MARKER_FACTOR = 0.85
ISSUE_CONFIDENCE_CAP = 0.5
DEFAULT_NEXT_STEP = (
    "Choose one point, add a sociological term and a piece of evidence, and explain how it answers the question."
)
BLANK_FEEDBACK = "There is no answer to mark yet. Write your answer, then submit it again."


class AOMarks(BaseModel):
    AO1: int = Field(default=0, ge=0)
    AO2: int = Field(default=0, ge=0)
    AO3: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return self.AO1 + self.AO2 + self.AO3


class EssayMarking(BaseModel):
    marks_awarded: int = Field(ge=0)
    level: int | None = Field(default=None, ge=0, le=5)
    ao_marks: AOMarks | None = None
    credited_points: list[str] = Field(default_factory=list, max_length=8)
    missing: list[str] = Field(default_factory=list, max_length=6)
    feedback_summary: str = Field(default="", max_length=800)
    what_went_well: str | None = Field(default=None, max_length=400)
    next_step: str = Field(default="", max_length=400)
    mistakes: list[DiagnosedMistake] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class EssayInput:
    marks: int
    stem: str
    context: str | None
    command_word: str | None
    mark_scheme: str
    answer: str
    evaluator_role: str
    second_evaluator_role: str | None
    dual_marking: bool
    max_disagreement: Mapping[str, int]
    confidence_threshold: float
    calibrated: bool
    level_guide: Mapping[str, str]
    mistake_categories: tuple[str, ...]
    mistake_labels: tuple[str, ...]


@dataclass(frozen=True)
class MarkerResult:
    role: str
    model: str
    marking: EssayMarking


@dataclass(frozen=True)
class EssayOutcome:
    status: Literal["final", "needs_review"]
    marks_awarded: int
    marks_available: int
    confidence: float
    checks: TextChecks
    level: int | None
    markers: list[dict[str, Any]]
    feedback: dict[str, Any]
    mistakes: list[dict[str, Any]]
    issues: list[str]
    model: str
    prompt_version: str
    cost_usd: float | None = None
    pipeline: str = field(default=PIPELINE)
    pipeline_version: str = field(default=PIPELINE_VERSION)

    @property
    def rubric_version(self) -> str:
        return f"{PROMPT}/{self.prompt_version}"

    @property
    def criterion_scores(self) -> dict[str, Any]:
        return {"markers": self.markers}

    @property
    def tool_results(self) -> dict[str, Any]:
        return {"text_checks": self.checks.as_dict()}

    @property
    def agreement_record(self) -> dict[str, Any]:
        return {"dual_marking": len(self.markers) > 1, "issues": self.issues, "model": self.model}

    @property
    def skill_marks(self) -> dict[str, float] | None:
        """The first marker's AO split, scaled to the agreed mark (skill profile evidence)."""
        split = self.markers[0].get("ao_marks") if self.markers else None
        total = sum(split.values()) if split else 0
        if not split or total <= 0:
            return None
        return {code: round(value * self.marks_awarded / total, 2) for code, value in split.items()}


def uses_levels(marks: int) -> bool:
    return marks >= LEVELS_FROM_MARKS


def guide_for(marks: int, guide: Mapping[str, str]) -> tuple[str, str]:
    if uses_levels(marks):
        return "levels", guide.get(str(marks)) or guide.get("points", "")
    return "points", guide.get("points", "")


def agreement_issues(inp: EssayInput, results: Sequence[MarkerResult]) -> list[str]:
    issues: list[str] = []
    for r in results:
        m = r.marking
        if m.marks_awarded > inp.marks:
            issues.append("marks_exceed_available")
        if m.ao_marks is not None and m.ao_marks.total != m.marks_awarded:
            issues.append("ao_marks_do_not_add_up")
        if uses_levels(inp.marks) and m.level is None:
            issues.append("level_missing")
    if len(results) == 2:
        a, b = results[0].marking, results[1].marking
        if uses_levels(inp.marks):
            if (
                a.level is not None
                and b.level is not None
                and abs(a.level - b.level) > inp.max_disagreement.get("essay_levels", 0)
            ):
                issues.append("level_disagreement")
            if abs(a.marks_awarded - b.marks_awarded) > max(2, inp.max_disagreement.get("short_answer_marks", 1)):
                issues.append("marks_disagreement")
        elif abs(a.marks_awarded - b.marks_awarded) > inp.max_disagreement.get("short_answer_marks", 1):
            issues.append("marks_disagreement")
    return list(dict.fromkeys(issues))


def combine(inp: EssayInput, results: Sequence[MarkerResult], issues: Sequence[str]) -> tuple[int, int | None, float]:
    """Agreed marks = the lower of the two when they differ by one (conservative), else the rounded-down mean."""
    marks = [min(r.marking.marks_awarded, inp.marks) for r in results]
    awarded = min(marks) if len(marks) == 2 and abs(marks[0] - marks[1]) <= 1 else sum(marks) // len(marks)
    levels = [r.marking.level for r in results if r.marking.level is not None]
    level = min(levels) if levels else None
    confidence = min(r.marking.confidence for r in results)
    if len(results) == 1:
        confidence *= SINGLE_MARKER_FACTOR
    if issues:
        confidence = min(confidence, ISSUE_CONFIDENCE_CAP)
    return awarded, level, round(confidence, 3)


def _variables(inp: EssayInput, checks: TextChecks) -> dict[str, str]:
    mode, guide = guide_for(inp.marks, inp.level_guide)
    return {
        "marks": str(inp.marks),
        "command_word": checks.command_word or "not stated",
        "mode": mode,
        "context": inp.context or "none",
        "stem": inp.stem,
        "mark_scheme": inp.mark_scheme or "(not available)",
        "guide": guide or "(use the mark scheme)",
        "word_count": str(checks.word_count),
        "judgement_expected": str(checks.judgement_expected).lower(),
        "conclusion_present": str(checks.conclusion_present).lower(),
        "answer": inp.answer,
        "mistake_categories": ", ".join(inp.mistake_categories),
        "mistake_labels": ", ".join(inp.mistake_labels),
    }


def evaluate(gateway: LLMGateway, ctx: CallContext, inp: EssayInput) -> EssayOutcome:
    checks = check_answer(inp.answer, marks=inp.marks, command_word=inp.command_word, stem=inp.stem)
    if checks.word_count == 0:  # nothing to mark: no LLM call
        return EssayOutcome(
            status="final",
            marks_awarded=0,
            marks_available=inp.marks,
            confidence=1.0,
            checks=checks,
            level=0 if uses_levels(inp.marks) else None,
            markers=[],
            feedback={"summary": BLANK_FEEDBACK, "what_went_well": None, "next_step": DEFAULT_NEXT_STEP},
            mistakes=[],
            issues=[],
            model="none",
            prompt_version="none",
        )

    variables = _variables(inp, checks)
    first = gateway.structured(inp.evaluator_role, PROMPT, variables, EssayMarking, ctx)  # LLMError propagates
    results = [MarkerResult(inp.evaluator_role, first.model, first.value)]
    cost = first.cost_usd or 0.0
    issues: list[str] = []
    if inp.dual_marking and inp.second_evaluator_role:
        try:
            second = gateway.structured(inp.second_evaluator_role, PROMPT, variables, EssayMarking, ctx)
            results.append(MarkerResult(inp.second_evaluator_role, second.model, second.value))
            cost += second.cost_usd or 0.0
        except LLMError:
            issues.append("second_marker_unavailable")
    issues = [*issues, *agreement_issues(inp, results)]
    if not inp.calibrated:
        issues.append("evaluator_not_calibrated")  # AC-E5
    awarded, level, confidence = combine(inp, results, issues)
    status: Literal["final", "needs_review"] = (
        "final" if not issues and confidence >= inp.confidence_threshold else "needs_review"
    )
    primary = results[0].marking
    return EssayOutcome(
        status=status,
        marks_awarded=awarded,
        marks_available=inp.marks,
        confidence=confidence,
        checks=checks,
        level=level,
        markers=[
            {
                "role": r.role,
                "model": r.model,
                "marks_awarded": r.marking.marks_awarded,
                "level": r.marking.level,
                "ao_marks": r.marking.ao_marks.model_dump() if r.marking.ao_marks else None,
                "credited_points": r.marking.credited_points,
                "missing": r.marking.missing,
                "confidence": r.marking.confidence,
            }
            for r in results
        ],
        feedback={
            "summary": repair_json_escapes(primary.feedback_summary.strip()),
            "what_went_well": primary.what_went_well,
            "next_step": primary.next_step.strip() or DEFAULT_NEXT_STEP,
        },
        mistakes=[
            {**m.model_dump(), "fingerprint": fingerprint(m, inp.mistake_labels)}
            for m in primary.mistakes
            if m.category in inp.mistake_categories and awarded < inp.marks
        ],
        issues=issues,
        model="+".join(r.model for r in results),
        prompt_version=first.prompt_version,
        cost_usd=cost,
    )
