"""Study-test scoring (pure): unanswered items score 0; a score is final only when everything is marked and reviewed."""

from __future__ import annotations

from uuid import uuid4

from app.modules.assessment.service import ItemMark, ScoreEntry, score_form


def mark(status: str, awarded: float) -> ItemMark:
    return ItemMark(evaluation_id=uuid4(), status=status, marks_awarded=awarded)


def test_final_score_counts_unanswered_as_zero() -> None:
    entries = [
        ScoreEntry(marks=2, answered=True, mark=mark("final", 2)),
        ScoreEntry(marks=3, answered=True, mark=mark("overridden", 1)),
        ScoreEntry(marks=4, answered=False, mark=None),
    ]
    score = score_form(entries, submitted=True)
    assert (score.awarded, score.available, score.answered, score.final) == (3, 9, 2, True)


def test_score_is_not_final_while_marking_or_review_is_outstanding() -> None:
    unmarked = [ScoreEntry(marks=2, answered=True, mark=None)]
    assert score_form(unmarked, submitted=True).model_dump() == {
        "awarded": 0,
        "available": 2,
        "answered": 1,
        "unmarked": 1,
        "pending_review": 0,
        "final": False,
    }
    provisional = score_form([ScoreEntry(marks=2, answered=True, mark=mark("needs_review", 1))], submitted=True)
    assert (provisional.pending_review, provisional.final) == (1, False)
    complete = [ScoreEntry(marks=2, answered=True, mark=mark("final", 2))]
    assert score_form(complete, submitted=False).final is False  # never final before submission


def test_a_total_with_a_provisional_mark_has_no_number_for_her() -> None:
    """AC-E6: a test total that includes a mark waiting for review is not a number the student sees."""
    from app.modules.assessment.schemas import ScoreOut
    from app.modules.assessment.service import _student_score

    pending = ScoreOut(awarded=9, available=14, answered=1, unmarked=0, pending_review=1, final=False)
    assert _student_score(pending, is_student=True).awarded is None
    assert _student_score(pending, is_student=False).awarded == 9  # the parent checks it
    final = pending.model_copy(update={"pending_review": 0, "final": True})
    assert _student_score(final, is_student=True).awarded == 9
