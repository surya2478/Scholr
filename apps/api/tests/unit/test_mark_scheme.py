"""Mark-scheme table parser. All layouts are synthetic, built in the test; no real mark-scheme content."""

from __future__ import annotations

import pymupdf
import pytest

from app.modules.assessment.mark_scheme import (
    MINUS,
    RECURRING_DOT,
    UNMAPPED,
    Item,
    Rule,
    accept_ranges,
    accuracy_hints,
    looks_tabular,
    map_glyph,
    numbers,
    parse_document,
    parse_marks,
    render_cell,
    resolve_ref,
)

# ---------------------------------------------------------------------------
# Synthetic PDF layout: Question | Answer | Marks | Partial Marks
# ---------------------------------------------------------------------------

COLS = (50.0, 110.0, 280.0, 325.0, 545.0)
TABLE_BOTTOM = 760.0


def table_page(doc: pymupdf.Document, *, rules_at: tuple[float, ...] = ()) -> tuple[pymupdf.Page, float]:
    """A page with the header row and column rules. Returns (page, y below the header)."""
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 50), "0000/99  Synthetic test mark scheme", fontsize=11)  # page header, above the table
    for x, label in zip((60, 180, 290, 400), ("Question", "Answer", "Marks", "Partial Marks"), strict=True):
        page.insert_text((x, 74), label, fontsize=11)
    for x in COLS:
        page.draw_line((x, 60), (x, TABLE_BOTTOM), width=0.5)
    page.draw_line((COLS[0], 60), (COLS[-1], 60), width=0.5)
    page.draw_line((COLS[0], 80), (COLS[-1], 80), width=0.5)
    for extra in rules_at:  # a short rule inside the Answer column (a small table in a cell)
        page.draw_line((extra, 300), (extra, 340), width=0.5)
    page.insert_text((60, 800), "Page 1 of 2", fontsize=8)  # footer in the Question column, below the table
    return page, 80.0


def row_rule(page: pymupdf.Page, y: float, *, from_x: float = COLS[0]) -> None:
    page.draw_line((from_x, y), (COLS[-1], y), width=0.5)


def text(page: pymupdf.Page, x: float, baseline: float, s: str, size: float = 11) -> None:
    page.insert_text((x, baseline), s, fontsize=size)


def fraction(page: pymupdf.Page, x: float, bar_y: float, numerator: str, denominator: str) -> float:
    """Numerator sitting on a short bar, denominator hanging below it. Returns the bar's right end."""
    width = max(pymupdf.get_text_length(s, fontsize=11) for s in (numerator, denominator)) + 2
    page.draw_line((x, bar_y), (x + width, bar_y), width=0.5)
    text(page, x + 1, bar_y - 3, numerator)
    text(page, x + 1, bar_y + 11, denominator)
    return x + width


def synthetic_mark_scheme() -> pymupdf.Document:
    doc = pymupdf.open()
    cover = doc.new_page(width=595, height=842)
    cover.insert_text((60, 100), "Synthetic cover page without a question table", fontsize=11)

    page, y = table_page(doc)
    # 1: two answer lines, integer marks, partial marks
    text(page, 75, y + 16, "1")
    text(page, 115, y + 16, "40")
    text(page, 115, y + 29, "-275")  # base-14 fonts cannot encode an en dash; map_glyph is tested separately
    text(page, 300, y + 16, "2")
    text(page, 330, y + 16, "B1 for each")
    row_rule(page, y + 40)
    # 2(a): "0.6 or" followed by a stacked fraction 3 over 5
    y += 40
    text(page, 65, y + 20, "2(a)")
    text(page, 115, y + 20, "0.6 or")
    fraction(page, 150, y + 16, "3", "5")
    text(page, 300, y + 20, "1")
    row_rule(page, y + 40)
    # 2(b): a method sub-row (M1) and a final-answer sub-row (A2) under one merged Question cell
    y += 40
    text(page, 65, y + 16, "2(b)")
    text(page, 115, y + 16, "146.46 - 1.46")
    text(page, 300, y + 16, "M1")
    row_rule(page, y + 24, from_x=COLS[1])  # the rule does not cross the Question column
    end = fraction(page, 115, y + 40, "29", "198")
    text(page, end + 4, y + 44, "cao")
    text(page, 300, y + 44, "A2")
    text(page, 330, y + 44, "A1 for a correct fraction")
    row_rule(page, y + 64)
    # 3: continues onto the next page
    y += 64
    text(page, 75, y + 16, "3")
    text(page, 115, y + 16, "146 or 146.2 to 146.3")
    text(page, 300, y + 16, "3")
    text(page, 330, y + 16, "M2 for a correct method")

    page, y = table_page(doc, rules_at=(150.0,))  # between the "Question" and "Answer" header words
    text(page, 330, y + 16, "or M1 for a partial method")  # continuation of 3: above the first ref on the page
    row_rule(page, y + 24)
    y += 24
    text(page, 75, y + 16, "4")
    text(page, 115, y + 16, "y = 2x ruled")
    text(page, 300, y + 16, "M2")
    text(page, 300, y + 29, "M1dep")
    text(page, 300, y + 42, "B2FT")
    row_rule(page, y + 50)
    y += 50
    text(page, 54, y + 16, "5(a)(vi)(a)", size=10)
    text(page, 115, y + 16, "17")
    text(page, 300, y + 16, "1")
    return doc


@pytest.fixture(scope="module")
def table():  # noqa: ANN201
    parsed = parse_document(synthetic_mark_scheme())
    assert parsed is not None
    return parsed


def test_rows_are_found_by_layout(table) -> None:  # noqa: ANN001
    assert [r.ref for r in table.rows] == ["1", "2(a)", "2(b)", "3", "4", "5(a)(vi)(a)"]
    assert table.pages == [2, 3]
    assert not [i for i in table.issues if "content_before_first_ref" in i or "unreadable" in i]


def test_marks_integer_or_summed_codes(table) -> None:  # noqa: ANN001
    marks = {r.ref: r.marks for r in table.rows}
    assert marks == {"1": 2, "2(a)": 1, "2(b)": 3, "3": 3, "4": 5, "5(a)(vi)(a)": 1}
    assert table.total_marks == 15
    assert looks_tabular(table, min_rows=5)


def test_multi_line_answer_keeps_both_values(table) -> None:  # noqa: ANN001
    row = table.by_ref()["1"]
    assert row.answer == "40\n-275"
    assert row.partial_marks == "B1 for each"
    assert numbers(row.answer) == {"40", "275"}


def test_stacked_fraction_becomes_inline(table) -> None:  # noqa: ANN001
    row = table.by_ref()["2(a)"]
    assert row.answer == "0.6 or 3/5"
    assert "fraction" in row.notation


def test_method_sub_row_is_not_the_answer(table) -> None:  # noqa: ANN001
    row = table.by_ref()["2(b)"]
    assert row.answer == "29/198 cao"
    assert row.method == "146.46 - 1.46"
    assert "cao" in row.accuracy_hints
    assert row.guidance.startswith(row.method)


def test_row_continues_across_pages(table) -> None:  # noqa: ANN001
    row = table.by_ref()["3"]
    assert row.pages == [2, 3]
    assert row.partial_marks == "M2 for a correct method\nor M1 for a partial method"
    assert row.accept_ranges == [("146.2", "146.3")]


def test_short_rule_inside_a_cell_is_not_a_column_boundary(table) -> None:  # noqa: ANN001
    # The answer text crosses x=150, where a short rule is drawn; the full-height rule at x=110 is the boundary.
    assert table.by_ref()["4"].answer == "y = 2x ruled"
    assert table.by_ref()["5(a)(vi)(a)"].answer == "17"


def test_drawn_diagram_in_answer_cell_is_flagged() -> None:
    doc = pymupdf.open()
    page, y = table_page(doc)
    text(page, 65, y + 16, "1(a)")
    page.draw_circle((180, y + 40), 20, width=0.5)
    text(page, 176, y + 44, "A")
    text(page, 300, y + 16, "1")
    row_rule(page, y + 70)
    text(page, 65, y + 86, "1(b)")
    text(page, 115, y + 86, "17")
    text(page, 300, y + 86, "1")
    parsed = parse_document(doc)
    assert parsed is not None
    rows = parsed.by_ref()
    assert "diagram" in rows["1(a)"].notation
    assert "diagram" not in rows["1(b)"].notation


def test_document_without_question_table_is_not_parsed() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 100), "Level 3 (7-9 marks): a well developed answer.", fontsize=11)
    assert parse_document(doc) is None
    assert not looks_tabular(None)


# ---------------------------------------------------------------------------
# Cell rendering from layout items
# ---------------------------------------------------------------------------


def test_superscript_becomes_power() -> None:
    items = [Item("x", 0, 0, 5, 12, 11), Item("2", 5, -1, 8, 7, 7)]
    assert render_cell(items, []) == "x^2"


def test_recurring_dot_marks_the_digit_below() -> None:
    items = [Item("0", 0, 0, 6, 12, 11), Item(".", 6, 0, 9, 12, 11), Item("4", 9, 0, 15, 12, 11)]
    items.append(Item("", 9.5, -3, 14.5, 9, 11, "dot"))
    assert render_cell(items, []) == f"0.4{RECURRING_DOT}"


def test_tall_brackets_around_stacked_lines_become_a_vector() -> None:
    pieces = [Item("(", 0, y, 4, y + 8, 11, "open") for y in (0, 8, 16)]
    pieces += [Item(")", 20, y, 24, y + 8, 11, "close") for y in (0, 8, 16)]
    content = [Item("3", 8, 0, 14, 12, 11), Item(MINUS, 8, 12, 12, 24, 11), Item("2", 12, 12, 18, 24, 11)]
    assert render_cell(pieces + content, []) == f"(3, {MINUS}2)"


def test_fraction_with_compound_parts_is_parenthesised() -> None:
    numerator = [Item("x", 10, 0, 15, 12, 11), Item("+", 15, 0, 21, 12, 11), Item("1", 21, 0, 27, 12, 11)]
    denominator = [Item("2", 15, 13, 21, 25, 11)]
    bar = Rule(9, 12.5, 28, 12.5, stroked=True)
    assert render_cell(numerator + denominator, [bar]) == "(x+1)/2"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("char", "font", "expected"),
    [
        ("", "Symbol", (MINUS, "char")),
        ("", "Symbol", ("π", "char")),
        ("", "Symbol", ("×", "char")),
        ("", "Symbol", ("(", "char")),
        ("", "Symbol", ("(", "open")),
        ("", "Symbol", (")", "close")),
        ("", "MTExtra", ("", "dot")),
        ("", "EuclidMathTwo", (UNMAPPED, "char")),
        ("–", "TimesNewRoman", (MINUS, "char")),
        ("7", "TimesNewRoman", ("7", "char")),
    ],
)
def test_map_glyph(char: str, font: str, expected: tuple[str, str]) -> None:
    assert map_glyph(char, font) == expected


@pytest.mark.parametrize(
    ("marks_text", "expected"),
    [("2", 2), ("M1\nA2", 3), ("M2\nM1dep\nA1", 4), ("B1\nB2FT\nB2\nB1", 6), ("", None), ("SC1", None)],
)
def test_parse_marks(marks_text: str, expected: int | None) -> None:
    assert parse_marks(marks_text) == expected


def test_resolve_ref() -> None:
    assert resolve_ref("7 (b) (ii)", None) == "7(b)(ii)"
    assert resolve_ref("(c)", "7(b)(ii)") == "7(c)"
    assert resolve_ref("(iii)", "7(b)(ii)") == "7(b)(iii)"
    assert resolve_ref("2(a)(vi)(b)", "2(a)(vi)(a)") == "2(a)(vi)(b)"
    assert resolve_ref("obtuse", "5(a)") is None


def test_ranges_hints_and_numbers() -> None:
    assert accept_ranges(f"x = {MINUS}0.5 to {MINUS}0.55") == [("-0.55", "-0.5")]
    assert accept_ranges("146 or 146.2 to 146.3") == [("146.2", "146.3")]
    assert accuracy_hints("19.5 oe final answer correct to 1 dp") == ["oe", "final_answer", "dp:1"]
    assert numbers("12 000 or 0.60") == {"12000", "0.6"}
    assert numbers(f"0.4{RECURRING_DOT}6{RECURRING_DOT}") == {"0.46"}
