"""Write the Crucible's debates: perspectives on a real essay question, from her coursebook (learn/crucible.py).

For each topic of a subject whose config has `debates`, the highest-mark essay question in the bank is paired with
the coursebook excerpts on it; the `crucible_writer` role sets out the perspectives on the Batch API; the guard
keeps only cited, unnamed-unless-cited, uncopied perspectives; and nothing reaches her until a person approves it.

Usage (from apps/api):
  uv run python -m app.jobs.crucible --subject igcse-sociology                 # estimate only, no calls
  uv run python -m app.jobs.crucible --subject igcse-sociology --run           # write the missing ones (Batch API)
  uv run python -m app.jobs.crucible --subject igcse-sociology --review        # print what is stored
  uv run python -m app.jobs.crucible --subject igcse-sociology --approve 2.2 6.1 | --reject 3.4
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.db import session_scope
from app.jobs import batching
from app.jobs.walkthroughs import objectives
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import BatchItem, CallContext
from app.modules.identity.models import Tenant
from app.modules.learn import crucible
from app.modules.learn import service as learn
from app.modules.learn.models import Lesson

COST_PER_DEBATE_USD = 0.0005  # gemini-2.5-flash-lite:batch, ~8k tokens in and ~1k out, rounded up
ATTEMPTS = 2


def review(pairs: list[tuple[UUID, str]]) -> None:
    with session_scope(user_id=None, role="system") as s:
        for oid, code in pairs:
            row = s.scalar(select(Lesson).where(Lesson.objective_id == oid))
            debate = (row.content or {}).get("crucible") if row else None
            if not debate:
                continue
            print(f"\n[{'shown' if debate.get('approved') else 'waiting'}] {code}")
            for p in debate["perspectives"]:
                pages = ", ".join(f"p. {x['page']}" for x in p["sources"] if x.get("page"))
                print(f"  {p['perspective']} — {p['sociologist'] or '(no name)'}: {p['argument']} [{pages}]")
                if p.get("evidence"):
                    print(f"      evidence: {p['evidence']}")
            for q in debate.get("questions", []):
                print(f"  ? {q}")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.crucible")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--only", help="objective codes, comma separated")
    parser.add_argument("--redo", action="store_true", help="write again where one is stored")
    parser.add_argument("--run", action="store_true", help="make the calls; without it, print the estimate only")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--approve", nargs="+", metavar="CODE")
    parser.add_argument("--reject", nargs="+", metavar="CODE")
    args = parser.parse_args(argv[1:])

    only = {x.strip() for x in args.only.split(",")} if args.only else None
    if args.approve or args.reject:
        chosen = objectives(args.subject, set(args.approve or args.reject))
        with session_scope(user_id=None, role="system") as s:
            done = [c for oid, c in chosen if learn.decide_crucible(s, oid, approved=bool(args.approve))]
        print(f"{'approved' if args.approve else 'rejected'} {len(done)}: {', '.join(done) or 'none stored'}")
        return
    pairs = objectives(args.subject, only)
    if args.review:
        review(pairs)
        return

    gateway = build_gateway()
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        stored = {
            row.objective_id
            for row in s.scalars(select(Lesson).where(Lesson.objective_id.in_([o for o, _ in pairs])))
            if (row.content or {}).get("crucible")
        }
    if tenant_id is None:
        raise SystemExit("no household seeded (app.seed.household)")
    ctx = CallContext(request_id=f"crucible-prep:{datetime.now(UTC):%Y%m%d%H%M%S}", tenant_id=tenant_id)
    prepared: dict[str, tuple[str, learn.PreparedCrucible]] = {}
    for oid, code in pairs:
        if oid in stored and not args.redo:
            continue
        with session_scope(user_id=None, role="system") as s:
            p = learn.prepare_crucible(s, gateway, ctx, oid)
        if p is not None:
            prepared[str(oid)] = (code, p)
    role = load_roles().role(learn.CRUCIBLE_ROLE)
    print(
        f"{args.subject}: {len(prepared)} debates to write, estimate ${len(prepared) * COST_PER_DEBATE_USD:.3f} "
        f"(model {role.batch_model or role.model})",
        flush=True,
    )
    if not args.run or not prepared:
        return
    now = datetime.now(UTC)
    kept, dropped, cost = [], [], 0.0
    pending = dict(prepared)
    for attempt in range(ATTEMPTS):  # a debate the guard throws out is asked for once more (a fresh draft)
        if not pending:
            break
        got, failed, spent_here = batching.run(
            gateway,
            learn.CRUCIBLE_ROLE,
            learn.CRUCIBLE_PROMPT,
            [BatchItem(cid, p.variables) for cid, (_, p) in pending.items()],
            crucible.CrucibleDraft,
            tenant_id,
            tag=f"crucible-{args.subject}",
        )
        cost += spent_here
        retry = {}
        for cid, (code, p) in pending.items():
            if cid not in got:
                dropped.append(f"{code} ({failed.get(cid, 'missing')})")
                continue
            content, report = learn.finish_crucible(p, got[cid])
            if content is None:
                if attempt + 1 < ATTEMPTS:
                    retry[cid] = (code, p)
                else:
                    dropped.append(f"{code} (only {report['kept']} perspective(s) passed the checks)")
                continue
            with session_scope(user_id=None, role="system") as s:
                learn.record_crucible(s, p.objective_id, content, now=now)
            kept.append(code)
        pending = retry
    print(f"kept {len(kept)}: {', '.join(kept)}\nnot kept {len(dropped)}: {'; '.join(dropped)}\ncost ${cost:.4f}")


if __name__ == "__main__":
    main(sys.argv)
