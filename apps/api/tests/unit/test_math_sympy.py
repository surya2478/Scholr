import pytest

from app.tools.math_sympy import (
    MathParseError,
    NumericSpec,
    check_numeric,
    equivalent,
    parse_math,
    strip_units,
)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("(x+3)(y+5)", "xy + 5x + 3y + 15"),
        ("2x^2+3x", "3*x + 2*x**2"),
        (r"\frac{3}{5}", "0.6"),
        ("3(2m+5t)(2m-5t)", "12m^2 - 75t^2"),
        ("√16", "4"),
        ("x = 10", "10"),
        ("7n + 4", "4 + 7*n"),
        ("2×3", "6"),
    ],
)
def test_equivalent_forms(a: str, b: str) -> None:
    assert equivalent(a, b)


def test_not_equivalent() -> None:
    assert not equivalent("7n+4", "7n+3")


@pytest.mark.parametrize(
    "bad",
    [
        "__import__('os').system('dir')",
        "(1).real",
        "lambda x: x",
        "9^9^9^9^9",
        "2^99999",
        "x" * 300,
        "1,2",
        "",
    ],
)
def test_rejects_unsafe_or_invalid_input(bad: str) -> None:
    with pytest.raises(MathParseError):
        parse_math(bad)


def test_strip_units() -> None:
    assert strip_units("146.26 cm²") == "146.26"
    assert strip_units("$ 3375") == "3375"
    assert strip_units("218.7°") == "218.7"


# Shape area from 0580/21 June 2024 Q7(a): triangle 12.8 x 12.8 / 2 plus semicircle of diameter 12.8.
AREA = NumericSpec(exact="(1/2)*12.8*12.8 + pi*6.4^2/2", accept_ranges=(("146.2", "146.3"),))


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        ("146", "correct"),
        ("146.3", "correct"),
        ("146.26 cm²", "correct"),
        ("150", "insufficient_accuracy"),
        ("145", "incorrect"),
        ("abc?", "unparseable"),
    ],
)
def test_area_accuracy(answer: str, status: str) -> None:
    assert check_numeric(answer, AREA).status == status


def test_three_sig_figs_without_range() -> None:
    spec = NumericSpec(exact="(1/2)*12.8*12.8 + pi*6.4^2/2")
    assert check_numeric("146.26", spec).status == "correct"
    assert check_numeric("146", spec).status == "correct"


def test_exact_value_must_be_exact() -> None:
    car = NumericSpec(exact="8000*(0.75)^3")  # 3375 exactly
    assert check_numeric("3375", car).status == "correct"
    assert check_numeric("3375.00", car).status == "correct"
    assert check_numeric("3380", car).status == "insufficient_accuracy"
    assert check_numeric("3400", car).status == "insufficient_accuracy"
    assert check_numeric("3370", car).status == "incorrect"


def test_irrational_from_decimals_is_not_treated_as_exact() -> None:
    # Compound interest rate r from 1500 -> 1656.73 in 8 years (~1.2500%).
    rate = NumericSpec(exact="((1656.73/1500)^(1/8) - 1)*100")
    assert check_numeric("1.25", rate).status == "correct"
    assert check_numeric("1.3", rate).status == "insufficient_accuracy"


def test_angle_one_decimal_place() -> None:
    angle = NumericSpec(exact="180 + asin(5/8)*180/pi", accuracy="dp", places=1)  # 218.68...
    assert check_numeric("218.7", angle).status == "correct"
    assert check_numeric("219", angle).status == "insufficient_accuracy"
    assert check_numeric("218.6", angle).status == "incorrect"


def test_fraction_answers() -> None:
    assert check_numeric("2/5", NumericSpec(exact="1 - 0.6")).status == "correct"
    assert check_numeric("0.4", NumericSpec(exact="1 - 0.6")).status == "correct"
    recurring = NumericSpec(exact="29/198", accuracy="exact")
    assert check_numeric("29/198", recurring).status == "correct"
    assert check_numeric("0.146", recurring).status == "insufficient_accuracy"
