"""Unit checking with Pint (app/tools/units.py): textbook spellings accepted, nonsense refused."""

from __future__ import annotations

import pytest

from app.tools import units


@pytest.mark.parametrize(
    "text",
    [
        "N",
        "m/s",
        "m/s^2",
        "m/s²",
        "$m/s^{2}$",
        "J/(kg °C)",
        "J/kg°C",
        "Ω",
        "\\Omega",
        "Pa",
        "kg m/s",
        "kg/m³",
        "g/cm^3",
        "W",
        "Hz",
        "°C",
        "km/s/Mpc",
        "\\text{N}",
        "N m",
    ],
)
def test_textbook_units_are_understood(text: str) -> None:
    assert units.is_unit(text), text


@pytest.mark.parametrize("text", ["", "none", "tiles", "metres per banana", "2", "blah/s"])
def test_non_units_are_refused(text: str) -> None:
    assert not units.is_unit(text), text


def test_an_explicit_no_unit_is_recognised_but_blank_is_not() -> None:
    assert units.is_no_unit("none") and units.is_no_unit("dimensionless")
    assert not units.is_no_unit("")


@pytest.mark.parametrize(
    ("text", "shown"),
    [("m/s^2", "m/s²"), ("$m/s^{2}$", "m/s²"), ("\Omega", "Ω"), ("kg/m^3", "kg/m³"), ("s^-1", "s⁻¹"), ("N", "N")],
)
def test_units_are_shown_as_a_textbook_prints_them(text: str, shown: str) -> None:
    assert units.display(text) == shown
    assert units.is_unit(shown)  # the display form still parses
