"""Idempotent concept-graph seed from content/curriculum/concepts-*.yaml.

Usage: uv run python -m app.seed.concepts ../../content/curriculum/concepts-maths-grade9.yaml [...]

A concept is curriculum-neutral. This seed writes `concept`, links it to the learning objectives of each
subject listed in the file (`objective_concept`), and records which concepts it is built on
(`concept_prerequisite`). Nothing here is student data.

YAML shape:
  subjects: [igcse-maths, iit-maths]            # every subject the file may reference
  concepts:
    - name: Factorisation
      description: ...
      note: ...                                  # why the mapping is what it is, when it needs saying
      prerequisites: [Expanding brackets]        # names of other concepts in the same file
      objectives: { igcse-maths: ["12.3"], iit-maths: [L5] }
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.modules.curriculum.models import Concept, ConceptPrerequisite, ObjectiveConcept, Subject
from app.modules.curriculum.service import objectives_by_code


class PrerequisiteIn(BaseModel):
    name: str
    strength: float = 1.0


class ConceptIn(BaseModel):
    name: str
    description: str | None = None
    note: str | None = None
    prerequisites: list[str | PrerequisiteIn] = Field(default_factory=list)
    objectives: dict[str, list[str]] = Field(default_factory=dict)

    def prerequisite_pairs(self) -> list[tuple[str, float]]:
        return [(p, 1.0) if isinstance(p, str) else (p.name, p.strength) for p in self.prerequisites]


class ConceptFile(BaseModel):
    subjects: list[str]
    concepts: list[ConceptIn]


class ConceptSeedError(ValueError):
    pass


def _subject_ids(s: Session, codes: list[str]) -> dict[str, UUID]:
    rows = s.execute(select(Subject.code, Subject.id).where(Subject.code.in_(codes))).all()
    found = {code: sid for code, sid in rows}
    missing = sorted(set(codes) - set(found))
    if missing:
        raise ConceptSeedError(f"unknown subjects {missing} — run the curriculum seed first")
    return found


def seed_concepts(s: Session, data: ConceptFile) -> dict[str, Any]:
    subject_ids = _subject_ids(s, data.subjects)
    objective_ids = {code: objectives_by_code(s, sid) for code, sid in subject_ids.items()}

    names = {c.name for c in data.concepts}
    for concept in data.concepts:
        unknown = [name for name, _ in concept.prerequisite_pairs() if name not in names]
        if unknown:
            raise ConceptSeedError(f"'{concept.name}' lists prerequisites not in this file: {unknown}")
        for subject_code in concept.objectives:
            if subject_code not in subject_ids:
                raise ConceptSeedError(f"'{concept.name}' maps to '{subject_code}', which the file does not list")

    rows: dict[str, Concept] = {}
    for concept in data.concepts:
        row = s.scalar(select(Concept).where(Concept.name == concept.name))
        if row is None:
            row = Concept(name=concept.name)
            s.add(row)
        row.description, row.note = concept.description, concept.note
        s.flush()
        rows[concept.name] = row

    links = missing_objectives = prerequisites = 0
    for concept in data.concepts:
        row = rows[concept.name]
        # The file is the whole truth for this concept: links it no longer lists are removed.
        wanted: set[UUID] = set()
        for subject_code, codes in concept.objectives.items():
            by_code = objective_ids[subject_code]
            for code in codes:
                found = by_code.get(code)
                if found is None:
                    missing_objectives += 1
                    print(f"  ! {concept.name}: {subject_code} has no objective '{code}'", file=sys.stderr)
                    continue
                wanted.add(found[0])
        existing = set(s.scalars(select(ObjectiveConcept.objective_id).where(ObjectiveConcept.concept_id == row.id)))
        for objective_id in wanted - existing:
            s.add(ObjectiveConcept(objective_id=objective_id, concept_id=row.id))
        if existing - wanted:
            s.execute(
                delete(ObjectiveConcept).where(
                    ObjectiveConcept.concept_id == row.id, ObjectiveConcept.objective_id.in_(list(existing - wanted))
                )
            )
        links += len(wanted)

        pairs = {rows[name].id: strength for name, strength in concept.prerequisite_pairs()}
        s.execute(delete(ConceptPrerequisite).where(ConceptPrerequisite.concept_id == row.id))
        for prerequisite_id, strength in pairs.items():
            s.add(ConceptPrerequisite(concept_id=row.id, prerequisite_id=prerequisite_id, strength=strength))
        prerequisites += len(pairs)

    s.flush()
    return {
        "concepts": len(rows),
        "objective_links": links,
        "prerequisites": prerequisites,
        "missing_objectives": missing_objectives,
    }


def load(path: Path) -> ConceptFile:
    return ConceptFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit("usage: python -m app.seed.concepts <concepts.yaml> [...]")
    for arg in argv[1:]:
        data = load(Path(arg))
        with session_scope(user_id=None, role="system") as s:
            result = seed_concepts(s, data)
        print(f"{Path(arg).name}: {result}")


if __name__ == "__main__":
    main(sys.argv)
