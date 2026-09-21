"""How long a topic page takes, and the steps it is made of (docs/STUDENT-APP.md AC-U13).

A topic page can be long, and an unbroken page of text with no visible end is the thing a fifteen-year-old
gives up on. So the page says what it is made of and roughly how long it takes — honestly: every number below
is computed from the content actually on the page, never invented, and a step counts as done only where the
record says she did it.

The estimate is deliberately plain: reading speed for prose, a slower rate for a worked example (it is read with
a pencil, not skimmed), and the examiner's own rule of thumb of about a minute a mark for questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

READING_WPM = 180  # a careful reader of her age on unfamiliar material, not a skim
WORKED_EXAMPLE_MINUTES = 2
MINUTES_PER_MARK = 1  # the usual IGCSE guide: a mark is about a minute
_MATH = re.compile(r"\$[^$]*\$")


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    minutes: int
    done: bool = False


def _words(text: str) -> int:
    return len(_MATH.sub(" x ", text).split())


def reading_minutes(lesson: dict) -> int:
    """Minutes to read one lesson: its prose at ``READING_WPM``, plus time for each worked example."""
    prose = [lesson.get("summary", ""), *(str(p) for p in lesson.get("pitfalls", []))]
    prose += [str(section.get("body", "")) for section in lesson.get("sections", [])]
    prose += [f"{t.get('term', '')} {t.get('meaning', '')}" for t in lesson.get("key_terms", [])]
    examples = lesson.get("worked_examples", [])
    minutes = sum(_words(text) for text in prose) / READING_WPM + len(examples) * WORKED_EXAMPLE_MINUTES
    return max(1, round(minutes))


def question_minutes(marks: int) -> int:
    return max(1, marks * MINUTES_PER_MARK)


def steps(
    *,
    lesson: dict | None,
    lesson_read: bool,
    worked_marks: int = 0,
    check_marks: int,
    check_answered: bool,
    exam_marks: int,
    exam_answered: bool,
) -> list[Step]:
    """The steps this page actually offers, in the order they appear on it.

    A step is listed only when the page has that part: a lessons-only subject has one step, a taught topic with
    no bank items has one too. `done` comes from her record — a lesson she has read, a question she has answered
    — so the count means the same tomorrow as it does now.
    """
    out: list[Step] = []
    if lesson is not None:
        # The worked exam question (AC-U16) is read with the lesson: about a minute a mark, like the question itself.
        worked = question_minutes(worked_marks) if worked_marks else 0
        out.append(Step("lesson", "Learn", reading_minutes(lesson) + worked, lesson_read))
    if check_marks:
        out.append(Step("check", "Check yourself", question_minutes(check_marks), check_answered))
    if exam_marks:
        out.append(Step("exam", "Exam questions", question_minutes(exam_marks), exam_answered))
    return out


def total_minutes(steps_: list[Step]) -> int:
    return sum(step.minutes for step in steps_)
