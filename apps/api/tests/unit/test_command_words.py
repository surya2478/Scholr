"""Command-word help comes only from a checked source in the subject config (review of 22 Sep 2026)."""

from __future__ import annotations

from app.modules.subjects import service as subjects


def test_sociology_has_cambridges_definitions_and_maths_has_none() -> None:
    words = subjects.taught_config_for("igcse-sociology").command_words
    assert words is not None and "coursebook" in words.source
    assert words.definitions["define"] == "Give precise meaning"
    assert all(k == k.lower() for k in words.definitions)  # matched against the bank's lower-case command words
    assert subjects.taught_config_for("igcse-maths").command_words is None
