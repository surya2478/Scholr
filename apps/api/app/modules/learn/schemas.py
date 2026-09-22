from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.assessment.schemas import ExaminerInsightsOut

Stage = Literal["taught", "lessons", "planned", "external"]


class SubjectCardOut(BaseModel):
    id: UUID
    code: str
    name: str
    syllabus_code: str | None
    stage: Stage
    objectives: int
    # Topics with evidence at Competent or above; None when she has no evidence in the subject yet.
    secure: int | None
    practised: int


class StreamOut(BaseModel):
    key: str
    name: str
    description: str
    status: Literal["open", "later"]
    subjects: list[SubjectCardOut] = Field(default_factory=list)


class ObjectiveCardOut(BaseModel):
    id: UUID
    code: str
    statement: str
    mastery_level: int | None  # None = no evidence yet (never shown as a zero)
    mastery_name: str | None
    items: int
    lesson: Literal["ready", "not_enough_material", "none"]
    school_led: bool  # a validation-study control topic before crossover (AC-U9)
    # External (IIT) lessons only: sessions logged that covered it, and whether any was flagged as hard.
    classes: int = 0
    struggled: bool = False


class ChapterOut(BaseModel):
    id: UUID
    code: str
    name: str
    objectives: list[ObjectiveCardOut] = Field(default_factory=list)
    chapters: list[ChapterOut] = Field(default_factory=list)


class SubjectLearnOut(BaseModel):
    subject: SubjectCardOut
    stream: str
    chapters: list[ChapterOut]


class SourceRefOut(BaseModel):
    title: str
    page: int | None


class LessonSectionOut(BaseModel):
    heading: str
    body: str
    sources: list[SourceRefOut]


class KeyTermOut(BaseModel):
    term: str
    meaning: str


class WorkedExampleOut(BaseModel):
    problem: str
    steps: list[str]
    final_answer: str
    unit: str | None = None  # checked with Pint where the subject's answers carry units
    checked: Literal["sympy"] | None  # "sympy": SymPy recomputed the answer before it was stored (AC-U5)
    sources: list[SourceRefOut]
    level: Literal["basic", "standard", "exam"] | None = None  # lesson v4: examples rise to exam standard


class DiagramOut(BaseModel):
    """A picture the page draws for itself (AC-U14): `data` is what the check computed, not what a model wrote."""

    kind: str
    caption: str
    data: dict
    sections: list[int] = Field(default_factory=list)  # the lesson sections it illustrates, numbered from 1


class LessonOut(BaseModel):
    id: UUID
    status: Literal["ready", "not_enough_material"]
    summary: str = ""
    sections: list[LessonSectionOut] = Field(default_factory=list)
    key_terms: list[KeyTermOut] = Field(default_factory=list)
    worked_examples: list[WorkedExampleOut] = Field(default_factory=list)
    diagrams: list[DiagramOut] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    generated_at: datetime
    note: str = (
        "Written by Scholr from your course books — page references show where to read more. "
        "Check anything that looks wrong with your teacher."
    )


class ItemCardOut(BaseModel):
    id: UUID
    source_ref: str | None
    label: str  # what she sees: "June 2025 · Paper 21 · Q17(b)(ii)", or "Practice question"
    marks: int
    command_word: str | None
    stem: str | None = None
    context: str | None = None


class MistakeCardOut(BaseModel):
    description: str
    occurrences: int
    status: str


class ConnectionOut(BaseModel):
    objective_id: UUID
    objective_code: str
    statement: str
    subject_name: str
    concept: str
    practicable: bool


class ClassLogOut(BaseModel):
    occurred_on: date
    kind: str
    title: str
    score: float | None
    max_score: float | None
    struggled: bool


class GroundOut(BaseModel):
    """An IGCSE objective an external lesson rests on and she is not yet secure in."""

    objective_id: UUID
    objective_code: str
    statement: str
    subject_name: str
    concept: str
    depth: int  # 0 = the IGCSE side of the same idea, 1+ = something it rests on
    practicable: bool  # False = syllabus only: revise from the course book
    reason: str


class ExternalLessonOut(BaseModel):
    """What Scholr adds to a lesson learnt elsewhere (docs/STUDENT-APP.md step 5): never the lesson itself."""

    classes: list[ClassLogOut] = Field(default_factory=list)
    ground: list[GroundOut] = Field(default_factory=list)
    warm_up: list[ItemCardOut] = Field(default_factory=list)


class StepOut(BaseModel):
    """One part of the topic page, with how long it takes and whether she has done it (AC-U13)."""

    key: str
    label: str
    minutes: int
    done: bool


class HowExaminedOut(BaseModel):
    """How the past papers in the bank ask about this topic, counted from the bank (AC-U16). No model."""

    asked: int  # past-paper questions on this topic in the bank
    marks_min: int
    marks_max: int
    papers: list[str]  # ["Paper 2", "Paper 4"]
    years: list[str]
    command_words: list[str]  # the most common first, e.g. ["solve", "by drawing"]


class WalkStepOut(BaseModel):
    text: str
    mark: str  # "M1", "A1", "B1" — a code the official mark scheme awards — or "" for a step that earns none


class WorkedExamOut(BaseModel):
    """One real past-paper question solved to full marks (AC-U16). Its final answer passed the same check that
    marks her answers, and every mark named is one the official scheme awards."""

    item_id: UUID
    label: str  # "June 2025 · Paper 41 · Q14(c)"
    context: str | None
    stem: str
    marks: int
    has_diagram: bool
    steps: list[WalkStepOut]
    final_answer: str
    tip: str | None = None


class ExamLevelOut(BaseModel):
    # Whether this subject gets a solved exam question at all: only where code can check the answer (Maths), never
    # for Sociology, where Scholr does not write her exam answers (AC-R5).
    solves: bool = False
    how_examined: HowExaminedOut | None = None
    worked: WorkedExamOut | None = None
    # What the examiners wrote about the worked question — shown because its answer is already on the page (AC-R6).
    examiner: ExaminerInsightsOut | None = None


class TopicOut(BaseModel):
    objective: ObjectiveCardOut
    subject: SubjectCardOut
    path: list[str]  # chapter names from the top of the subject down
    lesson: LessonOut | None
    lesson_available: bool  # False for subjects Scholr does not explain, and for school-led topics
    tutor_available: bool = False  # the Tutor answers doubts only in subjects Scholr teaches
    check_yourself: list[ItemCardOut] = Field(default_factory=list)
    exam_questions: list[ItemCardOut] = Field(default_factory=list)
    exam_level: ExamLevelOut | None = None
    mistakes: list[MistakeCardOut] = Field(default_factory=list)
    connections: list[ConnectionOut] = Field(default_factory=list)
    external: ExternalLessonOut | None = None
    steps: list[StepOut] = Field(default_factory=list)  # what this page is made of, in page order
    minutes: int = 0  # the whole page, from its own content — never a guess
    notice: str | None = None


ChapterOut.model_rebuild()


class PastPaperItemOut(BaseModel):
    id: UUID
    source_ref: str | None
    series: str | None  # "MJ25"
    paper: str | None  # "21"
    question: str | None  # "3(a)(ii)"
    marks: int
    command_word: str | None
    # Her latest try: "marked", "provisional" (waiting for a parent's check), "answered" (not marked yet), or None.
    last_status: str | None = None
    last_marks: float | None = None


class PastPaperChapterOut(BaseModel):
    id: UUID | None  # None for questions not tagged to a topic yet
    code: str
    name: str
    items: list[PastPaperItemOut]


class PastPapersOut(BaseModel):
    """A subject's real past-paper questions, chapter by chapter (docs/STUDENT-APP.md step 4)."""

    subject: SubjectCardOut
    chapters: list[PastPaperChapterOut]
    series: list[str]
    total: int
    attempted: int


class VivaTopicOut(BaseModel):
    """A topic whose approved solved exam question can be defended step by step (docs/STUDENT-APP.md §19)."""

    objective_id: UUID
    code: str
    statement: str
    label: str  # "June 2025 · Paper 21 · Q18(d)"
    marks: int
    steps: int


class VivaQuestionOut(VivaTopicOut):
    context: str | None
    stem: str
    has_diagram: bool


class VivaStepIn(BaseModel):
    explanation: str = Field(min_length=1, max_length=1500)


class VivaStepOut(BaseModel):
    verdict: Literal["right", "partly", "not_yet", "safety"]
    what_was_right: str = ""
    missing: str = ""
    hint: str = ""
    # The reference step, for the page to show when she has got it or asks to see it.
    step_text: str = ""
    step_mark: str = ""
    last: bool = False
    safety_message: str | None = None  # set when her words raised a safety concern; nothing was judged
