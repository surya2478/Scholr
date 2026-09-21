"""Tag question-bank items with the assessment objectives they carry (AC-R1). No LLM.

Usage:
    uv run python -m app.jobs.ao_tag --subject igcse-sociology [--write]

The rule is `ao_tagging` in the subject's config, which comes from the syllabus's own "These questions
assess ..." statements. Without --write the job only reports what it would change, so the mapping can be
argued with before 259 rows move. Command words are normalised at the same time: the extractor kept the
paper's capitalisation, so "Describe" and "describe" were different command words to every reader of the
bank, including the drill picker.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.subjects import service as subjects


@dataclass
class Report:
    items: int = 0
    tagged: int = 0
    unchanged: int = 0
    untaggable: int = 0
    command_words_normalised: int = 0

    def line(self) -> str:
        return (
            f"{self.items} items: {self.tagged} newly tagged, {self.unchanged} already correct, "
            f"{self.untaggable} untaggable, {self.command_words_normalised} command words normalised"
        )


def run(s: Session, *, subject_code: str, write: bool) -> tuple[Report, Counter[str]]:
    config = subjects.taught_config_for(subject_code)
    if config.ao_tagging is None:
        raise SystemExit(f"{subject_code} has no ao_tagging block in its subject config")

    subject_id = s.scalar(select(Subject.id).where(Subject.code == subject_code))
    if subject_id is None:
        raise SystemExit(f"no subject {subject_code} — run the curriculum seed first")
    skills = curriculum.skills_by_code(s, subject_id)
    missing = [code for band in config.ao_tagging.bands for code in band.skills if code not in skills]
    if missing:
        raise SystemExit(f"config names skills the curriculum does not define: {sorted(set(missing))}")

    report, spread = Report(), Counter()
    rows = s.scalars(select(QuestionItem).where(QuestionItem.subject_id == subject_id)).all()
    for row in rows:
        report.items += 1
        wanted_codes = config.ao_tagging.skills_for(marks=row.marks, source_ref=row.source_ref)
        if not wanted_codes:
            report.untaggable += 1
            continue
        spread["+".join(wanted_codes)] += 1
        wanted: list[UUID] = [skills[code][0] for code in wanted_codes]
        if list(row.skill_ids or []) == wanted:
            report.unchanged += 1
        else:
            report.tagged += 1
            if write:
                row.skill_ids = wanted

        tidy = (row.command_word or "").strip().lower() or None
        if tidy != row.command_word:
            report.command_words_normalised += 1
            if write:
                row.command_word = tidy
    if write:
        s.flush()
    return report, spread


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Tag question items with assessment objectives (no LLM).")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--write", action="store_true", help="save the changes (otherwise report only)")
    args = parser.parse_args(argv)

    with session_scope(user_id=None, role="system") as s:
        report, spread = run(s, subject_code=args.subject, write=args.write)
    print(report.line())
    for combination, count in sorted(spread.items(), key=lambda kv: -kv[1]):
        print(f"  {combination:16} {count}")
    if not args.write:
        print("\n(nothing saved — re-run with --write)")


if __name__ == "__main__":
    main(sys.argv[1:])
