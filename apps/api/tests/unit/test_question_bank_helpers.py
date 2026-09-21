"""Question-bank helpers: per-paper extractor notes and NUL-safe item text (15 Sep 2026 fixes)."""

from __future__ import annotations

from app.jobs.question_bank import SUBJECT_NOTES, paper_notes
from app.modules.assessment.past_papers import ExtractedItem, _without_nul
from app.modules.knowledge.manifest import SourceIn


def source(**overrides: object) -> SourceIn:
    values: dict[str, object] = {
        "key": "0580-mj25-qp21",
        "title": "0580/21 Paper 2 (Extended) Question Paper, May/June 2025",
        "file": "mathematics/papacambridge/0580_s25_qp_21.pdf",
        "authority_tier": "A",
        "content_kind": "question",
        "exam_series": "MJ25",
        "component": "21",
        "publisher": "Cambridge University Press & Assessment (UCLES)",
        "owner": "Cambridge University Press & Assessment",
        "licence": "Private study only.",
        "acquired_via": "test",
        "private": True,
        "notes": "Current structure (from 2025): Paper 2 non-calculator, 2h, 100 marks.",
    }
    values.update(overrides)
    return SourceIn.model_validate(values)


def test_paper_notes_use_the_papers_own_manifest_notes() -> None:
    notes = paper_notes("igcse-maths", source())
    assert notes.startswith(SUBJECT_NOTES["igcse-maths"])
    assert "May/June 2025" in notes and "non-calculator" in notes
    assert "calculators allowed" not in notes.lower()  # the old fixed 2024 note is gone
    assert paper_notes("igcse-maths", source(notes=None)).endswith("May/June 2025")


def test_nul_characters_are_removed_from_item_text() -> None:
    item = ExtractedItem(
        ref="2(e)",
        stem="Calculate the mass.\n[Density = mass \x00 volume]",
        marks=3,
        answer_type="numeric",
        answer="1250",
        mark_scheme="M1 for \x00 used",
    )
    clean = _without_nul(item)
    assert "\x00" not in clean.stem and "\x00" not in clean.mark_scheme
    assert clean.stem.endswith("[Density = mass  volume]") and clean.marks == 3
