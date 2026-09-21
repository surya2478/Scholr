"""Committed eval datasets stay valid and large enough for the acceptance criteria that use them.

The evals themselves make LLM calls and run locally with a cost estimate first (CLAUDE.md); CI checks the datasets.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from app.modules.subjects.config import load_all

DATASETS = Path(__file__).resolve().parents[4] / "evals" / "datasets"


def _cases(name: str) -> list[dict]:
    data = yaml.safe_load((DATASETS / name / "cases.yaml").read_text(encoding="utf-8"))
    assert data.get("version"), "datasets carry a version"
    ids = [case["id"] for case in data["cases"]]
    assert len(ids) == len(set(ids)), "case ids must be unique"
    return data["cases"]


def test_tutor_dataset_covers_ac_k4() -> None:
    cases = _cases("tutor")
    subjects = set(load_all())
    assert {c["subject"] for c in cases} <= subjects
    assert {c["kind"] for c in cases} <= {"explain", "off_syllabus"}
    counts = Counter(c["subject"] for c in cases)
    assert counts["igcse-sociology"] >= 30  # AC-K4: at least 30 Sociology prompts
    assert all(c["message"].strip() for c in cases)


def test_safety_dataset_covers_ac_s4() -> None:
    cases = _cases("safety")
    assert len(cases) >= 60  # AC-S4
    assert {"crisis_response", "allow"} <= {c["expected"] for c in cases}


def test_retrieval_dataset_is_valid() -> None:
    assert _cases("retrieval")
