from __future__ import annotations

from app.modules.knowledge.ocr import merge_bands


def test_lines_repeated_in_the_overlap_are_dropped() -> None:
    top = "# Exercise 5\n\n5 Find\na $\\sqrt[4]{625}$\nb $\\sqrt[7]{2187}$"
    bottom = "a $\\sqrt[4]{625}$\nb  $\\sqrt[7]{2187}$\n\n6 Find the value of"
    assert merge_bands([top, bottom]) == (
        "# Exercise 5\n\n5 Find\na $\\sqrt[4]{625}$\nb $\\sqrt[7]{2187}$\n\n6 Find the value of\n"
    )


def test_fragment_of_previous_last_line_is_dropped() -> None:
    top = "The number of visitors doubles every month."
    bottom = "doubles every month.\nIn February there are $1200$."
    assert merge_bands([top, bottom]) == "The number of visitors doubles every month.\nIn February there are $1200$.\n"


def test_bands_without_shared_lines_are_kept_apart() -> None:
    assert merge_bands(["first band", "second band"]) == "first band\n\nsecond band\n"
