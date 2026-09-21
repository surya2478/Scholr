from __future__ import annotations

import pytest

from app.tools.answer_check import check_final_answer, compare_to_printed

# Specs shaped like question-bank rows; values written for these tests.
SEMICIRCLE = {
    "type": "numeric",
    "answer": "146 or 146.2 to 146.3",
    "exact": "(1/2)*12.8*12.8 + pi*6.4^2/2",
    "accuracy": "sf3",
    "accept_ranges": [["146.2", "146.3"]],
}


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        ("146", "correct"),
        ("146.26", "correct"),
        ("x = 146", "correct"),
        ("146 cm²", "correct"),
        ("150", "insufficient_accuracy"),
        ("140", "incorrect"),
        ("about one hundred", "unparseable"),
        ("", "unparseable"),
    ],
)
def test_numeric_with_exact_value(answer: str, status: str) -> None:
    assert check_final_answer(answer, SEMICIRCLE).status == status


@pytest.mark.parametrize(
    ("answer", "status"), [("3.237", "correct"), ("3.2", "insufficient_accuracy"), ("3.3", "incorrect")]
)
def test_numeric_printed_answer_only(answer: str, status: str) -> None:
    spec = {"type": "numeric", "answer": "3.24 cao", "exact": None, "accuracy": "sf3"}
    assert check_final_answer(answer, spec).status == status


@pytest.mark.parametrize(
    ("answer", "status"), [("38.68", "correct"), ("39", "insufficient_accuracy"), ("38.6", "incorrect")]
)
def test_angle_to_one_decimal_place(answer: str, status: str) -> None:
    assert compare_to_printed(answer, "38.7", accuracy="dp1_angle") == status


def test_bad_exact_value_falls_back_to_printed_answer() -> None:
    spec = {"type": "numeric", "answer": "12.5", "exact": "import os", "accuracy": "sf3"}
    verdict = check_final_answer("12.5", spec)
    assert (verdict.status, verdict.method) == ("correct", "printed_answer")


def test_expression_equivalence_and_form_commands() -> None:
    spec = {"type": "expression", "answer": "7n + 4 oe"}
    assert check_final_answer("4 + 7n", spec).status == "correct"
    assert check_final_answer("7n - 4", spec).status == "incorrect"
    factorise = {"type": "expression", "answer": "(x - 3)(x + 3)"}
    assert check_final_answer("x^2 - 9", factorise, command_word="Factorise").status == "not_checked"
    assert check_final_answer("(x+2)(x-3)", factorise, command_word="Factorise").status == "incorrect"


def test_coordinates_are_ordered_and_sets_are_not() -> None:
    point = {"type": "coordinates", "answer": "(3, −2)"}
    assert check_final_answer("(3,-2)", point).status == "correct"
    assert check_final_answer("(-2, 3)", point).status == "incorrect"
    pair = {"type": "set_of_values", "answer": "x = 10, y = −2"}
    assert check_final_answer("y = -2, x = 10", pair).status == "correct"
    assert check_final_answer("x = 10", pair).status == "incorrect"
    roots = {"type": "set_of_values", "answer": "1.62, -0.618"}
    assert check_final_answer("-0.618 and 1.618", roots).status == "correct"


def test_open_response_types_are_not_checked() -> None:
    assert check_final_answer("because the gradient is 2", {"type": "explanation"}).status == "not_checked"
