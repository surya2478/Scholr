"""Cognitive Mutation & Bug-Hunting Challenge Engine.

Inspired by Kurt VanLehn's Cognitive Bug Theory and software code reviews.
Students act as the 'Chief Examiner' inspecting synthetic flawed solutions,
pinpointing the derailed step, categorizing the misconception, and deciding
whether Cambridge method marks (M) or accuracy marks (A) should be awarded.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SolutionStep(BaseModel):
    step_number: int
    text: str
    is_bug: bool
    explanation: str


class BugChallenge(BaseModel):
    id: str
    title: str
    subject_category: str
    topic_name: str
    question_stem: str
    marks_available: int
    student_alias: str
    student_steps: list[SolutionStep]
    bug_type: str
    examiner_rationale: str
    marks_to_award: dict[str, Any]


class BugVerificationIn(BaseModel):
    selected_step: int
    selected_bug_type: str
    award_method_mark: bool


class BugVerificationOut(BaseModel):
    correct_step: bool
    correct_type: bool
    success: bool
    score: int  # 0 to 100
    examiner_report: str
    official_mark: str


# Curated catalog of real Cambridge & IIT Foundation cognitive traps
CHALLENGES: list[BugChallenge] = [
    BugChallenge(
        id="bug-math-01",
        title="The Illegal Cancellation Fallacy",
        subject_category="math_sciences",
        topic_name="Algebraic Fractions (0580)",
        question_stem="Simplify the expression: $\\frac{4x + 12}{4x}$",
        marks_available=2,
        student_alias="Candidate A",
        student_steps=[
            SolutionStep(
                step_number=1,
                text="Given: $\\frac{4x + 12}{4x}$",
                is_bug=False,
                explanation="Initial statement is copied correctly.",
            ),
            SolutionStep(
                step_number=2,
                text="Cancel $4x$ in the numerator with $4x$ in the denominator: $= 12$",
                is_bug=True,
                explanation=(
                    "Fatal algebraic bug: terms added together cannot be cancelled individually! "
                    "You must factorise the entire numerator first: $4(x + 3)$."
                ),
            ),
            SolutionStep(
                step_number=3,
                text="Final Answer: $12$",
                is_bug=False,
                explanation="Propagated from the faulty step 2.",
            ),
        ],
        bug_type="conceptual",
        examiner_rationale=(
            "Cambridge mark schemes strictly penalise cancelling terms across addition or subtraction. "
            "Correct step: $\\frac{4(x + 3)}{4x} = \\frac{x + 3}{x}$ or $1 + \\frac{3}{x}$."
        ),
        marks_to_award={"M1": False, "A1": False, "official": "0 / 2 Marks (B0)"},
    ),
    BugChallenge(
        id="bug-math-02",
        title="The Negative Bracket Distribution Trap",
        subject_category="math_sciences",
        topic_name="Linear Equations & Expansion (0580)",
        question_stem="Expand and simplify: $5 - 2(3x - 4)$",
        marks_available=2,
        student_alias="Candidate B",
        student_steps=[
            SolutionStep(
                step_number=1,
                text="Given: $5 - 2(3x - 4)$",
                is_bug=False,
                explanation="Initial expression.",
            ),
            SolutionStep(
                step_number=2,
                text="Expand brackets: $= 5 - 6x - 8$",
                is_bug=True,
                explanation=(
                    "Sign error: $-2 \\times (-4) = +8$, not $-8$. A negative times a negative produces a positive."
                ),
            ),
            SolutionStep(
                step_number=3,
                text="Simplify: $= -3 - 6x$",
                is_bug=False,
                explanation="Arithmetic following faulty step 2.",
            ),
        ],
        bug_type="calculation",
        examiner_rationale=(
            "Distributing negative factors across brackets is the single most frequent mark loss in Paper 2. "
            "Correct expansion: $5 - 6x + 8 = 13 - 6x$."
        ),
        marks_to_award={"M1": True, "A1": False, "official": "1 / 2 Marks (M1 for $-6x$, A0 for incorrect constant)"},
    ),
    BugChallenge(
        id="bug-math-03",
        title="The Root Eraser (Dividing by Variable)",
        subject_category="math_sciences",
        topic_name="Quadratic Equations (0580 & IIT)",
        question_stem="Solve the equation for $x$: $x^2 = 7x$",
        marks_available=2,
        student_alias="Candidate C",
        student_steps=[
            SolutionStep(
                step_number=1,
                text="Given: $x^2 = 7x$",
                is_bug=False,
                explanation="Initial equation.",
            ),
            SolutionStep(
                step_number=2,
                text="Divide both sides by $x$: $\\frac{x^2}{x} = \\frac{7x}{x}$",
                is_bug=True,
                explanation=(
                    "Dividing by a variable that could be zero erases a valid root ($x = 0$)! "
                    "You must factorise: $x^2 - 7x = 0 \\implies x(x - 7) = 0$."
                ),
            ),
            SolutionStep(
                step_number=3,
                text="Result: $x = 7$",
                is_bug=False,
                explanation="Only one of the two solutions found.",
            ),
        ],
        bug_type="conceptual",
        examiner_rationale=(
            "Quadratic equations have up to two roots. Dividing through by $x$ loses the root $x = 0$, "
            "costing the accuracy mark A1 in both Cambridge and JEE Foundation."
        ),
        marks_to_award={"M1": True, "A1": False, "official": "1 / 2 Marks (B1 for 7, B0 for missing 0)"},
    ),
    BugChallenge(
        id="bug-phys-01",
        title="The Apex Acceleration Fallacy",
        subject_category="physical_sciences",
        topic_name="Kinematics & Gravity (0625 & IIT)",
        question_stem=(
            "A ball is thrown vertically upward. State the velocity and acceleration at the very highest point."
        ),
        marks_available=2,
        student_alias="Candidate D",
        student_steps=[
            SolutionStep(
                step_number=1,
                text=(
                    "At the highest point, the ball momentarily stops moving, so vertical velocity $v = 0\\text{ m/s}$."
                ),
                is_bug=False,
                explanation="Correct: instantaneous vertical velocity is zero at the zenith.",
            ),
            SolutionStep(
                step_number=2,
                text="Because the ball is stopped, there is no motion, therefore acceleration $a = 0\\text{ m/s}^2$.",
                is_bug=True,
                explanation=(
                    "Gravity never turns off! Earth's gravitational field continues exerting a downward force $mg$, "
                    "so acceleration remains $9.8\\text{ m/s}^2$ downward."
                ),
            ),
        ],
        bug_type="conceptual",
        examiner_rationale=(
            "Conflating zero instantaneous velocity with zero acceleration is an elite physics misconception. "
            "If acceleration were zero at the top, the ball would float in mid-air forever!"
        ),
        marks_to_award={"M1": True, "A1": False, "official": "1 / 2 Marks (1 mark for $v=0$, 0 for acceleration)"},
    ),
    BugChallenge(
        id="bug-soc-01",
        title="Validity vs Reliability Conflation",
        subject_category="social_sciences",
        topic_name="Research Methods (0495)",
        question_stem="Explain one advantage of using closed-question questionnaires in sociological research.",
        marks_available=2,
        student_alias="Candidate E",
        student_steps=[
            SolutionStep(
                step_number=1,
                text="Closed questions provide standardised answers with pre-coded choices.",
                is_bug=False,
                explanation="Accurate description of closed questionnaires.",
            ),
            SolutionStep(
                step_number=2,
                text=(
                    "This makes the research highly valid because respondents give deep, "
                    "truthful accounts of their subjective meanings."
                ),
                is_bug=True,
                explanation=(
                    "Closed questionnaires produce high reliability (replicability), NOT high validity. "
                    "Pre-coded options limit depth and may lack genuine validity."
                ),
            ),
        ],
        bug_type="vocabulary",
        examiner_rationale=(
            "Confusing validity (truthfulness, depth) with reliability (repeatability, consistency) "
            "is the #1 conceptual error cited in Cambridge Principal Examiner reports for 0495 Paper 1."
        ),
        marks_to_award={
            "M1": True,
            "A1": False,
            "official": "1 / 2 Marks (1 mark for closed questions feature, 0 for incorrect validity claim)",
        },
    ),
]


def list_challenges(subject: str | None = None) -> list[BugChallenge]:
    """Return bug hunting cases, optionally filtered by subject category."""
    if not subject:
        return CHALLENGES
    return [c for c in CHALLENGES if c.subject_category.lower() == subject.lower()]


def get_challenge(challenge_id: str) -> BugChallenge | None:
    """Retrieve a single bug challenge by ID."""
    for c in CHALLENGES:
        if c.id == challenge_id:
            return c
    return None


def verify_challenge(challenge_id: str, submission: BugVerificationIn) -> BugVerificationOut:
    """Verify student's Chief Examiner decision."""
    challenge = get_challenge(challenge_id)
    if not challenge:
        return BugVerificationOut(
            correct_step=False,
            correct_type=False,
            success=False,
            score=0,
            examiner_report="Challenge not found.",
            official_mark="0 / 0",
        )

    actual_bug_step = next(s for s in challenge.student_steps if s.is_bug)
    correct_step = submission.selected_step == actual_bug_step.step_number
    correct_type = submission.selected_bug_type.lower() == challenge.bug_type.lower()

    score = 0
    if correct_step:
        score += 60
    if correct_type:
        score += 40

    success = correct_step and score >= 60

    report = (
        f"Step {actual_bug_step.step_number} was the fatal breakdown: {actual_bug_step.explanation} "
        f"{challenge.examiner_rationale}"
    )

    return BugVerificationOut(
        correct_step=correct_step,
        correct_type=correct_type,
        success=success,
        score=score,
        examiner_report=report,
        official_mark=challenge.marks_to_award.get("official", "Marked"),
    )
