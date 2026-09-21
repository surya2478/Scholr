"""Every table with student_id must be covered by an RLS migration."""

import importlib.util
from pathlib import Path

import app.models_registry  # noqa: F401
from app.core.db import student_scoped_tables

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"


def _covered_tables() -> set[str]:
    covered: set[str] = set()
    for path in MIGRATIONS.glob("*.py"):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ("STUDENT_TABLES", "NULLABLE_STUDENT_TABLES", "SYSTEM_READ_TABLES"):
            covered.update(getattr(module, name, ()))
    return covered


def test_all_student_scoped_tables_have_rls() -> None:
    missing = set(student_scoped_tables()) - _covered_tables()
    assert not missing, f"add an RLS migration for: {sorted(missing)}"
