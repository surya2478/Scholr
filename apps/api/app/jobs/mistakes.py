"""Rebuild the mistake bank from the event log (mistakes.recompute), e.g. after a rule change.

    python -m app.jobs.mistakes rebuild [--dry-run]

The bank is a projection: rebuilding never touches `learning_event`, only the rows derived from it. Run after the
spaced-repair rule (14 Nov 2026) so existing patterns get their due dates, and any already repaired close.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.modules.events.models import LearningEvent
from app.modules.mistakes import service as mistakes
from app.modules.mistakes.models import MistakePattern


def rebuild(*, apply: bool) -> str:
    with session_scope(user_id=None, role="system") as s:
        before = {r.id: (r.objective_id, r.status, r.due_on) for r in s.scalars(select(MistakePattern))}
        touched: dict[tuple[UUID, UUID], set[UUID]] = defaultdict(set)
        for tenant_id, student_id, objective_ids in s.execute(
            select(LearningEvent.tenant_id, LearningEvent.student_id, LearningEvent.objective_ids).where(
                LearningEvent.type == "mistake_diagnosed"
            )
        ):
            touched[(tenant_id, student_id)].update(objective_ids or ())
        for (tenant_id, student_id), objective_ids in touched.items():
            mistakes.recompute(s, tenant_id=tenant_id, student_id=student_id, objective_ids=sorted(objective_ids))
        after = list(s.scalars(select(MistakePattern)))
        lines = [
            f"{r.objective_id}: {before.get(r.id, (None, 'new', None))[1]} -> {r.status}, due {r.due_on}" for r in after
        ]
        if not apply:
            s.rollback()
    verb = "rebuilt" if apply else "would rebuild"
    return "\n".join([*lines, f"{verb} {len(after)} pattern(s) for {len(touched)} student(s)"])


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.mistakes")
    parser.add_argument("command", choices=["rebuild"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])
    print(rebuild(apply=not args.dry_run), flush=True)


if __name__ == "__main__":
    main(sys.argv)
