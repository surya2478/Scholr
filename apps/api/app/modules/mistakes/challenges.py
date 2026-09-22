"""Bug Hunter: find the wrong step in a candidate's working, as an examiner would (review of 22 Sep 2026).

Every challenge is built from a checked source — a person-approved walkthrough (AC-U16): a real past-paper question
whose steps passed the mark-scheme checks. Code, not a model, introduces ONE slip: it changes the result of one
calculation step. SymPy confirms that step is now false and every other step still holds (``exam.arithmetic_holds``),
so there is exactly one bug to find. (Carrying the wrong value forward made later steps false too, 22 Sep 2026.)

What the method-mark answer is follows from the mark the official scheme gives that step: an M mark is for the
method, so an arithmetic slip keeps it; an A or B mark is for the correct value, so it is lost. That is the
convention printed at the front of every Cambridge mark scheme, not a claim about this question. What the examiners
wrote about the real question comes from their report, attributed (AC-R6).

The challenge sent to the page never says which step is wrong; only the verdict does.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.modules.assessment import service as assessment
from app.modules.assessment.schemas import ExaminerInsightsOut
from app.modules.learn import exam
from app.modules.learn import service as learn

BUG_TYPE = "calculation"
_MATH = re.compile(r"\$([^$]+)\$")
_RESULT = re.compile(r"(=\s*)(-?\d+(?:\.\d+)?)")
_MARK = re.compile(r"^(SC|[MAB])\d$")


class ChallengeStep(BaseModel):
    step_number: int
    text: str


class BugChallenge(BaseModel):
    """What the page shows: a candidate's working, with no hint of which step is wrong."""

    id: str  # the objective id of the walkthrough it was built from
    title: str
    topic_name: str
    label: str  # "June 2025 · Paper 21 · Q18(d)"
    question_context: str | None
    question_stem: str
    marks_available: int
    student_steps: list[ChallengeStep]
    final_answer: str


class BugVerificationIn(BaseModel):
    selected_step: int
    selected_bug_type: str
    award_method_mark: bool


class BugVerificationOut(BaseModel):
    correct_step: bool
    correct_type: bool
    correct_mark: bool = False  # her decision on the step's mark matched the mark scheme's convention
    success: bool
    score: int  # 0 to 100
    bug_step: int
    bug_explanation: str
    correct_text: str  # the step as it should read
    examiner_report: str
    official_mark: str
    examiner: ExaminerInsightsOut | None = None  # what the report said about the real question, attributed


@dataclass(frozen=True)
class _Built:
    challenge: BugChallenge
    bug_step: int
    old_value: str
    new_value: str
    correct_text: str
    step_mark: str
    item_id: UUID


def _wrong_value(value: str) -> str:
    """A plausible slip: the last digit moved by one ("18" -> "19", "2.5" -> "2.6", "-8" -> "-7")."""
    head, last = value[:-1], int(value[-1])
    return f"{head}{(last + 1) % 10}" if last != 9 else f"{head}8"


def _mutate_step(text: str) -> tuple[str, str, str] | None:
    """(new text, old value, new value) with the first numeric result of the step's maths changed, or None."""
    for segment in _MATH.finditer(text):
        found = _RESULT.search(segment.group(1))
        if not found:
            continue
        old = found.group(2)
        new = _wrong_value(old)
        body = segment.group(1)
        changed = body[: found.start(2)] + new + body[found.end(2) :]
        new_text = text[: segment.start(1)] + changed + text[segment.end(1) :]
        if not exam.arithmetic_holds([new_text]):  # SymPy agrees the step is now wrong
            return new_text, old, new
    return None


def build(w: learn.ApprovedWalkthrough) -> _Built | None:
    """One challenge per walkthrough: the slip goes in the first calculation step that carries a mark of its own,
    chosen the same way every time (so a challenge can be checked again from its id)."""
    candidates = [i for i, step in enumerate(w.steps) if _MARK.match(step.get("mark", "") or "")]
    start = int(hashlib.sha256(str(w.objective_id).encode()).hexdigest(), 16) % max(1, len(candidates))
    for index in candidates[start:] + candidates[:start]:
        mutated = _mutate_step(w.steps[index]["text"])
        if mutated is None:
            continue
        new_text, old, new = mutated
        steps = [
            ChallengeStep(step_number=i + 1, text=new_text if i == index else step["text"])
            for i, step in enumerate(w.steps)
        ]
        if not all(exam.arithmetic_holds([s.text]) for s in steps if s.step_number != index + 1):
            continue  # another step already fails the check: the bug would not be the only one
        return _Built(
            challenge=BugChallenge(
                id=str(w.objective_id),
                title=f"{w.code} {w.statement}",
                topic_name=w.statement,
                label=w.label,
                question_context=w.context,
                question_stem=w.stem,
                marks_available=w.marks,
                student_steps=steps,
                # The answer line follows the slip, as a candidate's would; it is not a step, so no second bug.
                final_answer=re.sub(rf"(?<![\d.]){re.escape(old)}(?![\d.])", new, w.final_answer),
            ),
            bug_step=index + 1,
            old_value=old,
            new_value=new,
            correct_text=w.steps[index]["text"],
            step_mark=w.steps[index]["mark"],
            item_id=w.item_id,
        )
    return None


def list_challenges(s: Session, *, subject_id: UUID | None = None) -> list[BugChallenge]:
    return [b.challenge for w in learn.approved_walkthroughs(s, subject_id) if (b := build(w)) is not None]


def verify_challenge(s: Session, challenge_id: str, submission: BugVerificationIn) -> BugVerificationOut:
    """Mark her examiner's decision: the faulty step (50), the kind of error (25), and whether the step's mark
    stands (25). She succeeds only if she found the step and got the mark decision right."""
    try:
        objective_id = UUID(challenge_id)
    except ValueError:
        raise not_found("challenge") from None
    built = next(
        (b for w in learn.approved_walkthroughs(s) if w.objective_id == objective_id and (b := build(w)) is not None),
        None,
    )
    if built is None:
        raise not_found("challenge")

    method_mark = built.step_mark.startswith("M")
    correct_step = submission.selected_step == built.bug_step
    correct_type = submission.selected_bug_type.lower() == BUG_TYPE
    correct_mark = submission.award_method_mark == method_mark
    score = (50 if correct_step else 0) + (25 if correct_type else 0) + (25 if correct_mark else 0)

    keeps = (
        f"In the mark scheme this step earns {built.step_mark}. An M mark is for the method, so a correct method "
        "with an arithmetic slip keeps it; the accuracy marks that need the right value are lost."
        if method_mark
        else f"In the mark scheme this step earns {built.step_mark}. That mark is for the correct value, so the slip "
        "loses it — and a later mark that needs this value goes too, unless the scheme allows follow-through."
    )
    return BugVerificationOut(
        correct_step=correct_step,
        correct_type=correct_type,
        correct_mark=correct_mark,
        success=correct_step and correct_mark,
        score=score,
        bug_step=built.bug_step,
        bug_explanation=f"Step {built.bug_step} gives {built.new_value} where the working gives {built.old_value}.",
        correct_text=built.correct_text,
        examiner_report=keeps,
        official_mark=f"This step: {built.step_mark} {'kept' if method_mark else 'lost'}",
        examiner=assessment.examiner_insights(s, built.item_id),
    )
