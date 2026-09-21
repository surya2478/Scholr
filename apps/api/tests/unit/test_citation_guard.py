"""Citations shown with a tutor reply (tutor eval finding ts13/ts31: off-syllabus replies cited unrelated excerpts)."""

from __future__ import annotations

from app.modules.tutoring.engine import GENERAL_LABEL, grounding_plan, usable_citations


def test_weak_material_is_never_shown_as_a_source() -> None:
    for state in ("LOW", "NONE"):
        assert usable_citations([1, 2], state=state, excerpts=3) == []
    assert grounding_plan("LOW", citation_critical=True).prefix == GENERAL_LABEL  # labelled, so nothing to cite


def test_grounded_replies_keep_valid_unique_citations() -> None:
    assert usable_citations([2, 0, 2, 5, 1], state="HIGH", excerpts=3) == [2, 1]
    assert usable_citations([3], state="MEDIUM", excerpts=3) == [3]
