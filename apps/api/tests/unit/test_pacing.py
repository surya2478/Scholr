"""What a topic page is made of and how long it takes (app/modules/learn/pacing.py, AC-U13).

The lesson below is fixture text written for this test.
"""

from __future__ import annotations

from app.modules.learn import pacing

LESSON = {
    "summary": " ".join(["word"] * 90),
    "sections": [{"heading": "One", "body": " ".join(["word"] * 270)}],
    "key_terms": [{"term": "Factor", "meaning": "Divides a number exactly."}],
    "pitfalls": ["Forgetting one and the number itself."],
    "worked_examples": [{"problem": "p", "steps": ["a"], "final_answer": "13"}],
}


def test_reading_time_counts_the_prose_and_slows_down_for_worked_examples() -> None:
    # 90 + 270 + 4 + 5 = 369 words at 180 wpm is about two minutes, plus two for the one worked example.
    assert pacing.reading_minutes(LESSON) == 4
    # Maths inside $...$ is read, not skimmed past, but it is not counted word by word either.
    dense = {"summary": "$x^2 + 2x + 1 = (x+1)^2$", "sections": [], "key_terms": [], "pitfalls": []}
    assert pacing.reading_minutes(dense) == 1  # never zero: a page always takes some time
    assert pacing.reading_minutes({}) == 1


def test_questions_are_about_a_minute_a_mark() -> None:
    assert pacing.question_minutes(6) == 6
    assert pacing.question_minutes(0) == 1


def test_a_page_lists_only_the_parts_it_has_and_marks_what_she_has_done() -> None:
    full = pacing.steps(
        lesson=LESSON, lesson_read=True, check_marks=4, check_answered=False, exam_marks=6, exam_answered=False
    )
    assert [(s.key, s.minutes, s.done) for s in full] == [
        ("lesson", 4, True),
        ("check", 4, False),
        ("exam", 6, False),
    ]
    assert pacing.total_minutes(full) == 14

    # A lessons-only subject (Physics, D4) has one step; a taught topic with an empty bank also has one.
    only_lesson = pacing.steps(
        lesson=LESSON, lesson_read=False, check_marks=0, check_answered=False, exam_marks=0, exam_answered=False
    )
    assert [s.key for s in only_lesson] == ["lesson"]
    # A topic whose lesson has not been written yet offers the questions and nothing else.
    no_lesson = pacing.steps(
        lesson=None, lesson_read=False, check_marks=2, check_answered=True, exam_marks=0, exam_answered=False
    )
    assert [(s.key, s.done) for s in no_lesson] == [("check", True)]
    assert (
        pacing.steps(
            lesson=None, lesson_read=False, check_marks=0, check_answered=False, exam_marks=0, exam_answered=False
        )
        == []
    )


def test_a_question_is_named_by_its_paper_or_called_practice() -> None:
    from app.modules.learn import labels

    assert labels.item_label("0580/21/MJ25/Q17(b)(ii)", "past_paper") == "June 2025 · Paper 21 · Q17(b)(ii)"
    assert labels.item_label("0495/11/ON24/Q2(a)", "past_paper") == "November 2024 · Paper 11 · Q2(a)"
    # A generated item's key means nothing to her, so it is never shown.
    assert labels.item_label("template/round_three_sf/0", "template") == labels.PRACTICE
    assert labels.item_label(None, "past_paper") == labels.PRACTICE
    # An unfamiliar shape is shown as it stands rather than guessed at.
    assert labels.item_label("0580-paper-two-q4", "past_paper") == "0580-paper-two-q4"
