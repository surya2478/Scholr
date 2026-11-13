"""Mark-scheme literacy: what each Cambridge mark code means, decided by its letters (evaluation/mark_codes.py)."""

from __future__ import annotations

from app.modules.evaluation import mark_codes


def test_codes_are_read_from_their_letters_only() -> None:
    assert [mark_codes.kind(c) for c in ("M1", "A1", "B2", "SC1", "FT", "m1")] == ["M", "A", "B", "SC", "FT", "M"]
    assert mark_codes.kind("1") is None and mark_codes.kind("") is None and mark_codes.kind("Q3") is None
    assert "method" in (mark_codes.meaning("M1") or "").lower()
    assert mark_codes.meaning("1") is None  # an unknown code gets no meaning rather than a guessed one


def test_the_method_note_appears_only_when_working_saved_marks() -> None:
    saved = [{"code": "M1", "awarded": True}, {"code": "A1", "awarded": False}]
    note = mark_codes.method_note(saved)
    assert note and "M1" in note and "working" in note
    assert mark_codes.method_note([{"code": "M1", "awarded": True}, {"code": "A1", "awarded": True}]) is None
    assert mark_codes.method_note([{"code": "M1", "awarded": False}, {"code": "A1", "awarded": False}]) is None
    assert mark_codes.method_note([{"code": "B1", "awarded": False}]) is None
