"""Deterministic tutor eval checks: AC-K3 (no answer without material) and AC-K4 (uncited sociology claims)."""

from __future__ import annotations

from app.jobs.tutor_eval import check_reply
from app.modules.tutoring.schemas import TutorReply


def reply(message: str, citations: list[int] | None = None, general: bool = False) -> TutorReply:
    return TutorReply(message=message, citations=citations or [], uses_general_knowledge=general)


def test_no_material_means_no_answer() -> None:  # AC-K3
    assert check_reply(None, chunks=0, citation_critical=True, answer_allowed=False, kind="off_syllabus").ok
    answered = check_reply(
        reply("Here is an answer."), chunks=0, citation_critical=True, answer_allowed=False, kind="explain"
    )
    assert answered.issues == ("answered_without_material",)


def test_uncited_sociologists_studies_and_statistics_are_flagged() -> None:  # AC-K4
    text = "Parsons (1955) argued the family stabilises adults, and 42% of marriages end in divorce."
    check = check_reply(reply(text), chunks=3, citation_critical=True, answer_allowed=True, kind="explain")
    assert set(check.issues) == {"uncited_named_sociologist", "uncited_study", "uncited_statistic"}
    assert check_reply(
        reply(text, citations=[1]), chunks=3, citation_critical=True, answer_allowed=True, kind="explain"
    ).ok
    assert check_reply(
        reply(text, general=True), chunks=3, citation_critical=True, answer_allowed=True, kind="explain"
    ).ok
    maths = check_reply(
        reply("About 50% of the area is shaded."),
        chunks=2,
        citation_critical=False,
        answer_allowed=True,
        kind="explain",
    )
    assert maths.ok  # statistics rules apply only to citation-critical subjects


def test_invalid_citation_indexes_are_flagged() -> None:
    check = check_reply(
        reply("Norms are rules.", citations=[4]), chunks=3, citation_critical=True, answer_allowed=True, kind="explain"
    )
    assert check.issues == ("invalid_citation_index",)
