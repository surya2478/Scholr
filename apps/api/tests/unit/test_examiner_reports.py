"""Examiner-report insights (AC-R6): which question a comment is about is found in code, and only short points
in our own words survive. The report below is synthetic test text laid out like a real one."""

from __future__ import annotations

from uuid import uuid4

from app.llm.gateway import CallContext
from app.modules.assessment import examiner_reports as er
from tests.fixtures.llm import scripted_gateway, user_prompt

HEAD = (
    "      Cambridge International General Certificate of Secondary Education\n"
    "                  0495 Sociology June 2025\n"
    "          Principal Examiner Report for Teachers\n"
)
SYNTHETIC_REPORT = {
    1: HEAD
    + """
SOCIOLOGY
             Paper 0495/11
Research Methods, Identity and
Inequality
Key messages
In Question 1(e) candidates described their chosen methods too briefly to reach the top level.
General comments
Most candidates attempted all the questions they were required to and managed their time sensibly.
Comments on specific questions
Question 1 Research methods
(a) (i)
Nearly every candidate picked out two findings from the source without difficulty at all.
(ii)
Stronger answers tied each reason back to a named feature of the source rather than to research in general.
(iii) Weaker answers listed problems with any research, which (a) is not what was asked for here.
""",
    2: HEAD
    + """
(b)
Two brief examples were enough; long explanations earned nothing extra for the candidates.
Question 2 Identity: self and society
Question 2 those candidates who chose it wrote at length about the family and the media in general.
(a)
Definitions that confused socialisation with socialising with friends did not gain any credit.
                                                  © 2025
""",
}


def test_segments_follow_the_reports_own_layout() -> None:
    segments = er.segment_report(SYNTHETIC_REPORT)
    assert [s.key for s in segments] == [
        "11:paper",
        "11:1(a)(i)",
        "11:1(a)(ii)",
        "11:1(a)(iii)",
        "11:1(b)",
        "11:2",
        "11:2(a)",
    ]
    by_key = {s.key: s for s in segments}
    # Running heads, the subject banner and the copyright line never leak into a segment.
    assert all("Principal Examiner" not in s.text and "©" not in s.text for s in segments)
    assert "SOCIOLOGY" not in by_key["11:paper"].text
    # A back-reference to "(a)" inside prose stays prose: parts only move forward.
    assert "which (a) is not" in by_key["11:1(a)(iii)"].text
    # "Question 2 those candidates..." is a wrapped sentence, not a heading.
    assert by_key["11:2"].text.startswith("Question 2 those candidates")
    assert by_key["11:1(b)"].pages == (2,)
    assert by_key["11:1(a)(i)"].syllabus_code == "0495"


def test_roman_after_h_is_a_letter_and_after_a_is_a_sub_part() -> None:
    text = "Paper 0580/41\nComments on specific questions\nQuestion 4\n" + "\n".join(
        f"({p}) comment on this part of the question, long enough to be kept as its own segment."
        for p in ["a", "i", "ii", "b", "c", "d", "e", "f", "g", "h", "i"]
    )
    refs = [s.question_ref for s in er.segment_report({1: text})]
    assert refs == ["4(a)", "4(a)(i)", "4(a)(ii)", "4(b)", "4(c)", "4(d)", "4(e)", "4(f)", "4(g)", "4(h)", "4(i)"]


def test_ancestor_refs() -> None:
    assert er.ancestor_refs("0495/11/MJ25/Q1(a)(ii)") == [
        "0495/11/MJ25/Q1(a)(ii)",
        "0495/11/MJ25/Q1(a)",
        "0495/11/MJ25/Q1",
    ]
    assert er.ancestor_refs("0495/21/MJ25/Q3") == ["0495/21/MJ25/Q3"]


def _segment(key: str) -> er.ReportSegment:
    return next(s for s in er.segment_report(SYNTHETIC_REPORT) if s.key == key)


def test_guard_drops_copied_and_long_points_and_keeps_our_own_words() -> None:
    seg = _segment("11:1(a)(ii)")
    result = er.guard(
        seg,
        [
            ("what_scored", "Link each reason to something specific in the source.", None),
            # Eight words straight from the report: copyright, and not our wording.
            ("advice", "Tied each reason back to a named feature of the source, please.", None),
            ("advice", " ".join(["word"] * 41), None),
            ("advice", "Link each reason to something specific in the source!", None),  # same words again
            ("praise", "Well done.", None),  # not a kind we store
        ],
    )
    assert [p.text for p in result.kept] == ["Link each reason to something specific in the source."]
    assert result.kept[0].question_ref == "1(a)(ii)"
    assert (result.copied, result.too_long, result.duplicate) == (1, 1, 1)


def test_a_question_segment_keeps_its_own_ref_whatever_the_model_says() -> None:
    result = er.guard(_segment("11:1(b)"), [("advice", "A short phrase per example is enough.", "2(a)")])
    assert result.kept[0].question_ref == "1(b)"


def test_a_paper_point_moves_to_a_question_only_if_the_report_names_it_there() -> None:
    seg = _segment("11:paper")
    known = ["1(a)(i)", "1(a)(ii)", "1(e)"]
    result = er.guard(
        seg,
        [
            ("advice", "Describe the chosen method in detail, not just name it.", "1(e)"),
            ("advice", "Plan time so every required question is attempted.", "2(a)"),  # not named in the text
            ("advice", "Keep an eye on the clock throughout.", None),
        ],
        known_refs=known,
    )
    assert [p.question_ref for p in result.kept] == ["1(e)", None, None]
    assert result.bad_ref == 1


def test_paraphrase_attributes_by_block_id_and_ignores_unknown_blocks() -> None:
    gateway, transport, _ = scripted_gateway()
    segments = [_segment("11:1(a)(i)"), _segment("11:1(a)(ii)")]
    transport.reply(
        {
            "points": [
                {"block": "11:1(a)(ii)", "kind": "what_scored", "text": "Use the source's own details."},
                {"block": "11:3(f)", "kind": "advice", "text": "Not a block it was given."},
            ]
        }
    )
    out = er.paraphrase(gateway, CallContext("t", uuid4()), paper_label="Synthetic report, Paper 11", segments=segments)
    assert out.by_segment == {"11:1(a)(i)": [], "11:1(a)(ii)": [("what_scored", "Use the source's own details.", None)]}
    assert out.unknown_blocks == 1
    prompt = user_prompt(transport.requests[0])
    assert '<block id="11:1(a)(ii)">' in prompt and "Synthetic report, Paper 11" in prompt
