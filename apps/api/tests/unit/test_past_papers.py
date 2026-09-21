from uuid import uuid4

import pytest

from app.llm.gateway import CallContext
from app.modules.assessment.mark_scheme import MarkSchemeRow, MarkSchemeTable
from app.modules.assessment.past_papers import (
    LOOP_RETRY_TEMPERATURE,
    PROMPT_V1,
    PROMPT_V2,
    ExtractedItem,
    ExtractedQuestion,
    PaperInput,
    ReferenceItem,
    answer_located,
    answer_type_issue,
    check_paper,
    check_paper_against_table,
    compare_extractions,
    extract_paper,
    first_numeric_answer,
    item_from_row,
    item_status,
    mark_scheme_rows,
    merge_pages,
    normalise_ref,
    numeric_issue,
    parent_of,
    parse_total_marks,
    recheck_transition,
    repair_item,
    table_disagreements,
)
from tests.fixtures.llm import scripted_gateway, user_prompt


def item(ref: str, marks: int = 2, **kw: object) -> ExtractedItem:
    base: dict[str, object] = {"stem": "s", "answer_type": "text_short", "answer": "a", "mark_scheme": "m"}
    base.update(kw)
    return ExtractedItem(ref=ref, marks=marks, **base)  # type: ignore[arg-type]


def test_normalise_ref() -> None:
    assert normalise_ref("7 (b) (ii)") == "7(b)(ii)"
    assert normalise_ref("Q12") == "12"
    assert normalise_ref("7(B)") == "7(b)"
    assert normalise_ref("7b") is None
    assert normalise_ref("(a)") is None
    assert parent_of("7(b)(ii)") == "7"


def test_parse_total_marks() -> None:
    assert parse_total_marks("INFORMATION\n The total mark for this paper is 130.") == 130
    assert parse_total_marks("no total") is None


def test_first_numeric_answer() -> None:
    assert first_numeric_answer("146 or 146.2 to 146.3") == "146"
    assert first_numeric_answer("x = 10, y = −2") == "10"
    assert first_numeric_answer("0.6 or 3/5") == "0.6"
    assert first_numeric_answer("y = 2x ruled") == "2"


def test_numeric_issue_accepts_consistent_answer() -> None:
    good = item(
        "7(a)",
        3,
        answer_type="numeric",
        answer="146 or 146.2 to 146.3",
        exact_value="(1/2)*12.8*12.8 + pi*6.4^2/2",
        accept_ranges=[("146.2", "146.3")],
    )
    assert numeric_issue(good) is None


def test_numeric_issue_flags_mismatch() -> None:
    wrong = item("9", 2, answer_type="numeric", answer="3375", exact_value="8000*(0.75)^2")
    assert numeric_issue(wrong) is not None


def test_numeric_issue_skips_non_numeric_or_missing_exact() -> None:
    assert numeric_issue(item("8", answer_type="expression", answer="7n + 4")) is None
    assert numeric_issue(item("9", answer_type="numeric", answer="3375")) is None
    assert (
        numeric_issue(item("9", answer_type="numeric", answer="3375", exact_value="import os"))
        == "exact_value_unparseable"
    )


def test_check_paper_marks_total_and_duplicates() -> None:
    items = [item("1", 2), item("2(a)", 1), item("2(b)", 2)]
    assert check_paper(items, expected_total=5).ok
    assert "marks_total:5!=6" in check_paper(items, expected_total=6).issues
    dup = check_paper([item("1", 2), item("1", 3)], expected_total=None)
    assert "duplicate_ref:1" in dup.issues


def test_numeric_issue_ignores_ranges_when_checking_exact_value() -> None:
    radians = item(
        "21",
        4,
        answer_type="numeric",
        answer="33.2 or 33.18…",
        exact_value="atan(6.5/sqrt(4^2+9.1^2))",
        accept_ranges=[("33.18", "33.2")],
    )
    assert numeric_issue(radians) is not None
    degrees = radians.model_copy(update={"exact_value": "atan(6.5/sqrt(4^2+9.1^2))*180/pi"})
    assert numeric_issue(degrees) is None


# Mimics the text layer of a Cambridge mark-scheme table (test data written for this test).
MARK_SCHEME = """Generic Marking Principles
1  Marks must be awarded positively.
Question            Answer            Marks                   Partial Marks

     3(a)     40                                  2  B1 for each
                 –275

     3(b)     24                                  2

     5(a)          3                             1
          0.6 or
                   5

     5(b)     1024                                1

    16(b)    17                                  1
"""


def test_mark_scheme_rows_skip_principles_and_indented_numbers() -> None:
    rows = mark_scheme_rows(MARK_SCHEME)
    assert list(rows) == ["3(a)", "3(b)", "5(a)", "5(b)", "16(b)"]
    assert mark_scheme_rows("no table here") == {}


@pytest.mark.parametrize(
    ("answer", "ref", "expected"),
    [
        ("Sequence A: 40; Sequence B: –275", "3(a)", True),
        ("Sequence A: 40, Sequence B: 24", "3(a)", False),  # value copied from the next part
        ("17", "16(b)", True),
        ("13", "16(b)", False),
        ("0.6 or 3/5", "5(a)", True),
        ("Shaded region outside M and N", "16(a)", None),  # nothing numeric to check
        ("42", "7", None),  # no row found for this ref: cannot check, not evidence of a wrong answer
    ],
)
def test_answer_located(answer: str, ref: str, expected: bool | None) -> None:
    assert answer_located(answer, ref, mark_scheme_rows(MARK_SCHEME)) is expected


@pytest.mark.parametrize(
    ("status", "reserved", "issues", "meta", "expected"),
    [
        ("verified", False, ["answer_not_in_mark_scheme"], {}, "unverified"),
        ("verified", True, ["answer_not_in_mark_scheme"], {}, None),  # study items are never changed
        ("verified", False, [], {}, None),
        ("unverified", False, [], {"recheck_issues": ["answer_not_in_mark_scheme"]}, "verified"),
        ("unverified", False, [], {"recheck_issues": ["x"], "item_issues": ["answer_exact_mismatch"]}, None),
        ("unverified", False, [], {"recheck_issues": ["x"], "paper_issues": ["marks_total:132!=130"]}, None),
        ("unverified", False, [], {}, None),  # unverified at extraction: a re-check cannot promote it
    ],
)
def test_recheck_transition(
    status: str, reserved: bool, issues: list[str], meta: dict[str, object], expected: str | None
) -> None:
    assert recheck_transition(status, reserved, issues, meta) == expected


def test_check_paper_flags_answers_missing_from_mark_scheme() -> None:
    wrong = item("16(b)", 1, answer_type="numeric", answer="13")
    check = check_paper([wrong], expected_total=None, mark_scheme_text=MARK_SCHEME)
    assert check.item_issues == {"16(b)": ["answer_not_in_mark_scheme"]}


def test_item_status_requires_clean_checks_and_known_objectives() -> None:
    oid, tid = uuid4(), uuid4()
    good = item("1", 2, objective_codes=["1.1"])
    check = check_paper([good], expected_total=2)
    assert item_status(good, check, {"1.1": (oid, tid)}) == ("verified", [], [(oid, tid)])
    status, issues, _ = item_status(item("1", 2, objective_codes=["9.9"]), check, {})
    assert (status, issues) == ("unverified", ["unknown_objectives:9.9"])
    assert item_status(good, check_paper([good], expected_total=3), {"1.1": (oid, tid)})[0] == "unverified"


def test_repair_item_restores_latex_backslashes() -> None:
    damaged = item("2", stem="Work out $3 \times 4$")  # TAB left by an unescaped backslash in model JSON
    assert repair_item(damaged).stem == "Work out $3 \\times 4$"


def test_compare_extractions_with_bank() -> None:
    reference = [
        ReferenceItem("1", 2, "numeric", "146 or 146.2 to 146.3", "(1/2)*12.8*12.8 + pi*6.4^2/2"),
        ReferenceItem("2(a)", 1, "expression", "7n + 4", None),
        ReferenceItem("3", 3, "numeric", "12", "12"),
    ]
    candidate = [
        item("1", 2, answer_type="numeric", answer="146", exact_value="81.92 + 20.48*pi"),
        item("2 (a)", 2, answer_type="expression", answer="7n+4"),
        item("4", 1),
    ]
    c = compare_extractions(reference, candidate, verified_refs={"1", "2(a)"})
    assert (c.matched, c.missing_refs, c.extra_refs) == (2, ["3"], ["4"])
    assert (c.marks_agree, c.type_agree, c.answer_agree) == (1, 2, 2)
    assert (c.exact_compared, c.exact_agree) == (1, 1)
    assert c.verified_disagreements == ["2(a)"]  # verified by the candidate, but with the wrong marks
    assert c.differences == {"2(a)": ["marks"]}


def paper_input() -> PaperInput:
    return PaperInput(
        syllabus_code="0000",
        component="21",
        series="TEST",
        label="Fixture paper",
        subject_notes="none",
        page_texts={1: "cover", 2: "1 Work out 3 + 4. [1]"},
        page_images={},
        mark_scheme_text="1 7 B1",
        objectives_prompt="",
        expected_total=None,
    )


PAGE_JSON = (
    '{"items": [{"ref": "1", "stem": "Work out 3 + 4.", "marks": 1, "answer_type": "numeric", '
    '"answer": "7", "mark_scheme": "B1 for 7"}]}'
)


def test_page_stuck_in_a_repetition_loop_is_retried_warmer() -> None:
    gateway, transport, _ = scripted_gateway()
    looping = '{"items": [{"ref": "1", "answer": "' + "–" * 50  # cut off mid-string
    transport.reply_text(looping)  # first attempt
    transport.reply_text(looping)  # gateway's repair attempt
    transport.reply_text(PAGE_JSON)  # fresh attempt at a higher temperature
    extraction = extract_paper(gateway, CallContext(request_id="t", tenant_id=uuid4()), paper_input())
    assert extraction.failed_pages == {}
    assert [i.ref for _, items in extraction.pages for i in items] == ["1"]
    assert [r.temperature for r in transport.requests] == [0.0, 0.0, LOOP_RETRY_TEMPERATURE]


def test_page_failing_after_warm_retry_is_recorded_not_fatal() -> None:
    gateway, transport, _ = scripted_gateway()
    for _ in range(4):
        transport.reply_text("not json")
    extraction = extract_paper(gateway, CallContext(request_id="t", tenant_id=uuid4()), paper_input())
    assert extraction.failed_pages == {2: "invalid_output"}
    assert extraction.pages == []


def test_merge_pages_keeps_first_and_records_pages() -> None:
    merged = merge_pages([(2, [item("1(a)"), item("1(b)")]), (3, [item("1 (b)"), item("2")])])
    assert [m[0].ref for m in merged] == ["1(a)", "1(b)", "2"]
    assert merged[1][1] == [2, 3]


def test_normalise_ref_fourth_level() -> None:
    assert normalise_ref("2 (a) (vi) (a)") == "2(a)(vi)(a)"
    assert parent_of("2(a)(vi)(a)") == "2"
    assert normalise_ref("7(a)(b)") is None


# ---------------------------------------------------------------------------
# Answers from a parsed mark-scheme table (prompt v2). Rows are test data written for these tests.
# ---------------------------------------------------------------------------


def ms_row(ref: str, marks: int | None, answer: str, **kw: object) -> MarkSchemeRow:
    base: dict[str, object] = {"method": "", "partial_marks": "", "marks_text": str(marks or ""), "pages": [2]}
    base.update(kw)
    return MarkSchemeRow(ref=ref, marks=marks, answer=answer, **base)  # type: ignore[arg-type]


def question(ref: str, **kw: object) -> ExtractedQuestion:
    base: dict[str, object] = {"stem": "s", "answer_type": "text_short"}
    base.update(kw)
    return ExtractedQuestion(ref=ref, **base)  # type: ignore[arg-type]


TABLE = MarkSchemeTable(
    rows=[
        ms_row("3(a)", 2, "40\n−275", partial_marks="B1 for each"),
        ms_row("16(b)", 1, "17"),
        ms_row("21", 4, "33.2 or 33.18…", method="tan = 6.5 / 9.9", partial_marks="M1 for a correct ratio"),
        ms_row("22", 1, ""),
    ],
    pages=[4],
)
ANGLE = "atan(6.5/sqrt(4^2+9.1^2))"


def test_item_from_row_takes_answer_marks_and_guidance_from_the_mark_scheme() -> None:
    built = item_from_row(question("21", answer_type="numeric", exact_value=ANGLE), TABLE.by_ref()["21"])
    assert (built.ref, built.marks, built.answer) == ("21", 4, "33.2 or 33.18…")
    assert built.mark_scheme == "tan = 6.5 / 9.9\nM1 for a correct ratio"
    assert built.exact_value == ANGLE


def test_check_paper_against_table_item_issues() -> None:
    rows = TABLE.by_ref()
    items = [
        item_from_row(question("3(a)", answer_type="set_of_values"), rows["3(a)"]),
        item_from_row(question("16(b)", answer_type="numeric", exact_value="17"), rows["16(b)"]),
        item_from_row(question("21", answer_type="numeric", exact_value=ANGLE, accuracy="dp1_angle"), rows["21"]),
        item_from_row(question("22", answer_type="drawing"), rows["22"]),
    ]
    check = check_paper_against_table(items, TABLE, expected_total=8, unmatched_refs=["9"])
    assert check.ok and check.advisories == ["ref_not_in_mark_scheme:9"]  # only the unmatched part is affected
    # exact value in radians for an answer in degrees; a row without an answer
    assert check.item_issues == {
        "9": ["ref_not_in_mark_scheme"],
        "21": ["answer_exact_mismatch:incorrect"],
        "22": ["mark_scheme_answer_empty"],
    }

    items[2] = items[2].model_copy(update={"exact_value": ANGLE + "*180/pi"})
    items[1] = items[1].model_copy(update={"marks": 2})
    check = check_paper_against_table(items, TABLE, expected_total=None)
    assert check.ok
    assert check.item_issues == {"16(b)": ["marks_disagree_mark_scheme"], "22": ["mark_scheme_answer_empty"]}


def test_check_paper_against_table_refs_and_totals() -> None:
    rows = TABLE.by_ref()
    items = [item_from_row(question(ref), rows[ref]) for ref in ("3(a)", "16(b)")]
    check = check_paper_against_table(items, TABLE, expected_total=9)
    assert check.ok  # totals and unextracted rows are advisories: each item is checked against its own row
    assert check.advisories == [
        "mark_scheme_ref_not_extracted:21",
        "mark_scheme_ref_not_extracted:22",
        "mark_scheme_total:8!=9",
        "marks_total:3!=9",
    ]


@pytest.mark.parametrize(
    ("ref", "marks", "answer", "expected"),
    [
        ("16(b)", 1, "17", []),
        ("16(b)", 1, "13", ["answer_disagree_mark_scheme"]),  # wrong answer key
        ("3(a)", 2, "Sequence A: 40, Sequence B: −275", []),
        ("3(a)", 2, "Sequence A: 40, Sequence B: 24", ["answer_disagree_mark_scheme"]),  # neighbouring row's value
        ("16(b)", 2, "17", ["marks_disagree_mark_scheme"]),
        ("7", 1, "42", ["ref_not_in_mark_scheme"]),
    ],
)
def test_table_disagreements(ref: str, marks: int, answer: str, expected: list[str]) -> None:
    assert table_disagreements(ref, marks, answer, TABLE.by_ref()) == expected


def test_v2_extraction_takes_answers_from_the_table_and_drops_unknown_refs() -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply(
        {
            "items": [
                {"ref": "16 (b)", "stem": "Write down the value.", "answer_type": "numeric", "exact_value": "17"},
                {"ref": "9", "stem": "A part the mark scheme does not have.", "answer_type": "text_short"},
            ]
        }
    )
    extraction = extract_paper(gateway, CallContext(request_id="t", tenant_id=uuid4()), paper_input(), table=TABLE)
    assert extraction.prompt_version == PROMPT_V2
    [(_, items)] = extraction.pages
    assert [(i.ref, i.marks, i.answer, i.exact_value) for i in items] == [("16(b)", 1, "17", "17")]
    assert extraction.unmatched_refs == ["9"]
    prompt = user_prompt(transport.requests[0])
    assert "16(b) [1]" in prompt
    assert "1 7 B1" not in prompt  # the mark-scheme text is not sent in v2


@pytest.mark.parametrize(
    ("answer_type", "answer", "expected"),
    [
        ("extended_response", "29/198 cao", "answer_type_inconsistent"),
        ("explanation", "y < x\nx < 6\n1 ⩽ y ⩽ 5 oe", "answer_type_inconsistent"),
        ("explanation", "Because angles on a straight line add to 180", None),
        ("numeric", "29/198", None),
        ("explanation", "", None),
    ],
)
def test_answer_type_issue(answer_type: str, answer: str, expected: str | None) -> None:
    assert answer_type_issue(answer_type, answer) == expected


def test_check_paper_against_table_flags_prose_types_and_diagram_answers() -> None:
    table = MarkSchemeTable(rows=[ms_row("1", 2, "40\n−275"), ms_row("2", 1, "M N", notation=["diagram"])], pages=[4])
    rows = table.by_ref()
    items = [
        item_from_row(question("1", answer_type="extended_response"), rows["1"]),
        item_from_row(question("2", answer_type="drawing"), rows["2"]),
    ]
    check = check_paper_against_table(items, table, expected_total=3)
    assert check.ok
    assert check.item_issues == {"1": ["answer_type_inconsistent"], "2": ["mark_scheme_answer_has_diagram"]}


def test_v1_extraction_pins_prompt_v1() -> None:
    gateway, transport, _ = scripted_gateway()
    transport.reply_text(PAGE_JSON)
    extraction = extract_paper(gateway, CallContext(request_id="t", tenant_id=uuid4()), paper_input())
    assert extraction.prompt_version == PROMPT_V1
    assert "1 7 B1" in user_prompt(transport.requests[0])
