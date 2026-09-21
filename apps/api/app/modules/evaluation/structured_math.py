"""structured_math evaluation pipeline v1 (ARCHITECTURE §12.1).

final answer -> deterministic tool verdict -> LLM examiner awards marks against the official mark scheme ->
consistency checks (the tool verdict and the awarded marks must agree, AC-E2) -> confidence -> final | needs_review.
No database access here: the caller loads inputs and persists the outcome.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.llm.gateway import CallContext, LLMGateway
from app.llm.text_repair import repair_json_escapes
from app.tools.answer_check import ToolVerdict, check_final_answer

PIPELINE = "structured_math"
PIPELINE_VERSION = "structured_math_v1"
PROMPT = "maths_mark"

DEFAULT_NEXT_STEP = "Try a similar question on this topic, showing each step of your working."
REENTER_NEXT_STEP = (
    "Write your final answer on its own as a number or expression (for example 3.24 or 2x + 1), then submit again."
)
TOOL_DECISIVE = frozenset({"correct", "incorrect", "insufficient_accuracy"})
TOOL_NOT_CORRECT = frozenset({"incorrect", "insufficient_accuracy", "unparseable"})
TOOL_AGREEMENT_BONUS = 0.05
PHOTO_CONFIDENCE_FACTOR = 0.95
ISSUE_CONFIDENCE_CAP = 0.5
_MARK_VALUE = re.compile(r"(\d+)$")


class MarkAward(BaseModel):
    code: str = Field(max_length=12)
    awarded: bool
    reason: str = Field(default="", max_length=400)


class DiagnosedMistake(BaseModel):
    category: str = Field(max_length=32)
    label: str = Field(max_length=48)
    severity: Literal["low", "medium", "high"]
    description: str = Field(max_length=400)


class MathMarking(BaseModel):
    awards: list[MarkAward] = Field(default_factory=list, max_length=20)
    marks_awarded: int = Field(ge=0)
    final_answer_correct: bool | None
    feedback_summary: str = Field(max_length=800)
    what_went_well: str | None = Field(default=None, max_length=400)
    next_step: str = Field(default="", max_length=400)
    mistakes: list[DiagnosedMistake] = Field(default_factory=list, max_length=5)
    confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class MathInput:
    marks: int
    stem: str
    context: str | None
    command_word: str | None
    answer_spec: dict[str, Any]
    mark_scheme: str
    working: str | None
    final_answer: str | None
    from_photo: bool
    evaluator_role: str
    confidence_threshold: float
    mistake_categories: tuple[str, ...]
    mistake_labels: tuple[str, ...]


@dataclass(frozen=True)
class MathOutcome:
    status: Literal["final", "needs_review"]
    marks_awarded: int
    marks_available: int
    confidence: float
    tool: ToolVerdict
    awards: list[dict[str, Any]]
    feedback: dict[str, Any]
    mistakes: list[dict[str, Any]]
    issues: list[str]
    model: str
    prompt_version: str
    cost_usd: float | None = None

    @property
    def tool_agreement(self) -> str:
        if self.tool.status not in TOOL_DECISIVE:
            return "not_applicable"
        return "disagree" if "tool_llm_disagreement" in self.issues else "agree"

    # Common outcome interface shared with essay_levels.EssayOutcome (used by evaluation.service.record).
    pipeline = PIPELINE
    pipeline_version = PIPELINE_VERSION
    level: int | None = None
    skill_marks: dict[str, float] | None = None  # the maths marker does not split marks by assessment objective

    @property
    def rubric_version(self) -> str:
        return f"{PROMPT}/{self.prompt_version}"

    @property
    def criterion_scores(self) -> dict[str, Any]:
        return {"awards": self.awards}

    @property
    def tool_results(self) -> dict[str, Any]:
        return {"final_answer": self.tool.as_dict()}

    @property
    def agreement_record(self) -> dict[str, Any]:
        return {"tool_llm": self.tool_agreement, "issues": self.issues, "model": self.model}


def fingerprint(mistake: DiagnosedMistake, labels: Sequence[str]) -> str:
    return f"{mistake.category}:{mistake.label if mistake.label in labels else 'other'}"


def _awarded_total(awards: Sequence[MarkAward]) -> int:
    total = 0
    for award in awards:
        if award.awarded:
            match = _MARK_VALUE.search(award.code.strip())
            total += int(match.group(1)) if match else 1
    return total


def consistency_issues(inp: MathInput, tool: ToolVerdict, marking: MathMarking) -> list[str]:
    issues: list[str] = []
    if marking.marks_awarded > inp.marks:
        issues.append("marks_exceed_available")
    if marking.awards and _awarded_total(marking.awards) != marking.marks_awarded:
        issues.append("award_sum_mismatch")
    if (tool.status == "correct" and marking.final_answer_correct is False) or (
        tool.status in TOOL_NOT_CORRECT and marking.final_answer_correct is True
    ):
        issues.append("tool_llm_disagreement")
    if tool.status in ("incorrect", "unparseable") and marking.marks_awarded >= inp.marks > 0:
        issues.append("full_marks_with_wrong_final_answer")
    if tool.status == "correct" and marking.marks_awarded < inp.marks:
        # A correct final answer normally earns every mark; a low-cost marker withholding marks gets a human look.
        issues.append("partial_marks_with_correct_final_answer")
    if tool.status == "unparseable":
        issues.append("final_answer_unparseable")
    if any(m.category not in inp.mistake_categories for m in marking.mistakes):
        issues.append("unknown_mistake_category")
    return list(dict.fromkeys(issues))


def combine_confidence(inp: MathInput, tool: ToolVerdict, marking: MathMarking, issues: Sequence[str]) -> float:
    confidence = marking.confidence
    if tool.status in TOOL_DECISIVE and "tool_llm_disagreement" not in issues:
        confidence = min(1.0, confidence + TOOL_AGREEMENT_BONUS)
    if inp.from_photo:
        confidence *= PHOTO_CONFIDENCE_FACTOR
    if issues:
        confidence = min(confidence, ISSUE_CONFIDENCE_CAP)
    return round(confidence, 3)


def _variables(inp: MathInput, tool: ToolVerdict) -> dict[str, str]:
    return {
        "marks": str(inp.marks),
        "context": inp.context or "none",
        "stem": inp.stem,
        "scheme_answer": str(inp.answer_spec.get("answer") or "see mark scheme"),
        "mark_scheme": inp.mark_scheme or "(no further guidance)",
        "working_source": "transcribed from photos and confirmed by the student" if inp.from_photo else "typed",
        "working": inp.working or "(no working shown)",
        "final_answer": inp.final_answer or "(none)",
        "tool_status": tool.status,
        "tool_detail": tool.detail,
        "mistake_categories": ", ".join(inp.mistake_categories),
        "mistake_labels": ", ".join(inp.mistake_labels),
    }


def repair_marking(marking: MathMarking) -> MathMarking:
    """Restore LaTeX backslashes that a model failed to escape in JSON (see app.llm.text_repair)."""
    return marking.model_copy(
        update={
            "feedback_summary": repair_json_escapes(marking.feedback_summary),
            "what_went_well": repair_json_escapes(marking.what_went_well) if marking.what_went_well else None,
            "next_step": repair_json_escapes(marking.next_step),
            "awards": [a.model_copy(update={"reason": repair_json_escapes(a.reason)}) for a in marking.awards],
            "mistakes": [
                m.model_copy(update={"description": repair_json_escapes(m.description)}) for m in marking.mistakes
            ],
        }
    )


def evaluate(gateway: LLMGateway, ctx: CallContext, inp: MathInput) -> MathOutcome:
    tool = check_final_answer(inp.final_answer, inp.answer_spec, command_word=inp.command_word)
    result = gateway.structured(inp.evaluator_role, PROMPT, _variables(inp, tool), MathMarking, ctx)
    marking = repair_marking(result.value)
    issues = consistency_issues(inp, tool, marking)
    confidence = combine_confidence(inp, tool, marking, issues)
    status: Literal["final", "needs_review"] = (
        "final" if not issues and confidence >= inp.confidence_threshold else "needs_review"
    )
    if "final_answer_unparseable" in issues:
        next_step = REENTER_NEXT_STEP
    else:
        next_step = marking.next_step.strip() or DEFAULT_NEXT_STEP
    return MathOutcome(
        status=status,
        marks_awarded=min(marking.marks_awarded, inp.marks),
        marks_available=inp.marks,
        confidence=confidence,
        tool=tool,
        awards=[a.model_dump() for a in marking.awards],
        feedback={
            "summary": marking.feedback_summary.strip(),
            "what_went_well": marking.what_went_well,
            "next_step": next_step,
        },
        # Mistakes explain lost marks: a full-marks answer never enters the mistake bank.
        mistakes=[
            {**m.model_dump(), "fingerprint": fingerprint(m, inp.mistake_labels)}
            for m in marking.mistakes
            if m.category in inp.mistake_categories and marking.marks_awarded < inp.marks
        ],
        issues=issues,
        model=result.model,
        prompt_version=result.prompt_version,
        cost_usd=result.cost_usd,
    )
