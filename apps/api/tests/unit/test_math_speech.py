from app.tools.math_speech import math_to_speech


def test_fractions() -> None:
    raw = r"The slope is $\frac{y_2 - y_1}{x_2 - x_1}$."
    spoken = math_to_speech(raw)
    assert "over" in spoken
    assert r"\frac" not in spoken
    assert "$" not in spoken


def test_powers_and_roots() -> None:
    raw = r"Pythagoras gives $c = \sqrt{a^2 + b^2}$."
    spoken = math_to_speech(raw)
    assert "the square root of" in spoken
    assert "squared" in spoken
    assert r"\sqrt" not in spoken


def test_equations_and_greek() -> None:
    raw = r"The area of a circle is $A = \pi r^2$ where $\theta \le 180^\circ$."
    spoken = math_to_speech(raw)
    assert "pi" in spoken
    assert "theta" in spoken
    assert "is less than or equal to" in spoken
    assert "degrees" in spoken


def test_units_and_markdown() -> None:
    raw = r"**Acceleration** is $9.8 \text{ m/s}^2$ and resistance is $50 \ \Omega$."
    spoken = math_to_speech(raw)
    assert "Acceleration" in spoken
    assert "**" not in spoken
    assert "meters per second squared" in spoken
    assert "ohms" in spoken


def test_citation_removal() -> None:
    raw = "Sociologist Oakley [1, 2] investigated conventional families."
    spoken = math_to_speech(raw)
    assert "[1, 2]" not in spoken
    assert "Oakley" in spoken
