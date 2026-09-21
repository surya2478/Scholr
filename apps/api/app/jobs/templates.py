"""Generate SymPy-verified practice items from parametric templates (no LLM).

Usage (from apps/api):
  uv run python -m app.jobs.templates generate --subject igcse-maths [--per-template 5] [--dry-run]
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.modules.assessment import templates
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.identity.models import Tenant
from app.modules.subjects import service as subjects


def generate(subject_code: str, per_template: int, dry_run: bool) -> None:
    config = subjects.taught_config_for(subject_code)
    template_file = templates.load_templates(config.key)
    created = skipped = rejected = 0
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        subject_id = s.scalar(select(Subject.id).where(Subject.code == subject_code))
        if tenant_id is None or subject_id is None:
            raise SystemExit("seed the curriculum and household first")
        objectives = curriculum.objectives_by_code(s, subject_id)
        existing = set(s.scalars(select(QuestionItem.source_ref).where(QuestionItem.origin == "template")))
        for spec in template_file.templates:
            if spec.objective not in objectives:
                print(f"{spec.id}: unknown objective {spec.objective} — skipped")
                continue
            objective_id, topic_id = objectives[spec.objective]
            for seed in range(per_template):
                item = templates.generate(spec, seed)
                if not item.verified:
                    rejected += 1
                    print(f"{item.source_ref}: rejected {item.issues}")
                    continue
                if item.source_ref in existing:
                    skipped += 1
                    continue
                created += 1
                if dry_run:
                    continue
                s.add(
                    QuestionItem(
                        tenant_id=tenant_id,
                        subject_id=subject_id,
                        origin="template",
                        source_ref=item.source_ref,
                        stem=item.stem,
                        marks=item.marks,
                        command_word=item.command_word,
                        objective_ids=[objective_id],
                        topic_ids=[topic_id],
                        difficulty=item.difficulty,
                        calculator_allowed=True,
                        answer_spec=item.answer_spec,
                        mark_scheme={"text": item.mark_scheme, "source": template_file.version},
                        verification_status="verified",
                        verified_by="sympy",
                        generator_version=templates.GENERATOR_VERSION,
                    )
                )
        if dry_run:
            s.rollback()
    print(f"created={created} already_present={skipped} rejected={rejected} dry_run={dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--subject", required=True)
    g.add_argument("--per-template", type=int, default=5)
    g.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    generate(args.subject, args.per_template, args.dry_run)


if __name__ == "__main__":
    main()
