"""Solve one real past-paper question per topic, step by step, for the topic page's exam level (AC-U16).

For each objective the question is picked by fixed rules (``learn.exam.pick_worked``); the model writes the steps
from the official mark scheme, and the guard keeps a walkthrough only when its final answer passes the check that
marks her answers and every mark it names is one the scheme awards. A walkthrough that fails replaces nothing.
Only subjects whose worked examples SymPy checks get one (Maths); Scholr does not write Sociology exam answers.

Usage (from apps/api):
  uv run python -m app.jobs.walkthroughs --subject igcse-maths                 # estimate only, no calls
  uv run python -m app.jobs.walkthroughs --subject igcse-maths --only 15.4,1.6 --run
  uv run python -m app.jobs.walkthroughs --subject igcse-maths --redo --run    # write them all again
  uv run python -m app.jobs.walkthroughs --subject igcse-maths --review        # print what is stored
  uv run python -m app.jobs.walkthroughs --subject igcse-maths --approve 15.4 1.6   # a person read them: show her
  uv run python -m app.jobs.walkthroughs --subject igcse-maths --reject 1.3        # delete these

Code checks each walkthrough's answer, marks, arithmetic and (for graph questions) its line, but not reasoning
written in words, so nothing reaches her until a person has read it and approved it (like the diagrams).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import session_scope
from app.jobs.lessons import spent
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext, LLMError
from app.llm.prompts import default_registry
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.identity.models import Tenant
from app.modules.learn import service as learn
from app.modules.learn.models import Lesson

REPORTS = API_ROOT.parents[1] / "evals" / "reports"
# Measured 21 Sep 2026: ~$0.0003 per call on gemini-2.5-flash-lite; up to two calls per topic, rounded up.
COST_PER_WALKTHROUGH_USD = 0.0008
ATTEMPTS = 2


def objectives(subject_code: str, only: set[str] | None) -> list[tuple[UUID, str]]:
    with session_scope(user_id=None, role="system") as s:
        subject = s.scalar(select(Subject).where(Subject.code == subject_code))
        if subject is None:
            raise SystemExit(f"unknown subject {subject_code}")
        tree = curriculum.subject_tree(s, subject.id)
        codes = {o.id: o.code for node in (tree.topics if tree else []) for o in _walk(node)}
    return [(oid, code) for oid, code in codes.items() if only is None or code in only]


def _walk(node):  # type: ignore[no-untyped-def]
    yield from node.objectives
    for child in node.children:
        yield from _walk(child)


def todo(pairs: list[tuple[UUID, str]], *, redo: bool) -> list[tuple[UUID, str, str]]:
    """(objective, code, source_ref) for every objective with a question worth solving and no walkthrough yet."""
    out = []
    with session_scope(user_id=None, role="system") as s:
        for oid, code in pairs:
            row = s.scalar(select(Lesson).where(Lesson.objective_id == oid))
            if row is None or ((row.content or {}).get("exam") and not redo):
                continue
            prepared = learn.prepare_walkthrough(s, oid)
            if prepared is not None:
                out.append((oid, code, prepared.item.source_ref or ""))
    return out


def write_one(objective_id: UUID, tenant_id: UUID) -> dict:
    gateway = build_gateway()
    now = datetime.now(UTC)
    ctx = CallContext(request_id=f"walkthrough:{objective_id}:{now:%Y%m%d%H%M%S}", tenant_id=tenant_id)
    with session_scope(user_id=None, role="system") as s:
        prepared = learn.prepare_walkthrough(s, objective_id)
    if prepared is None:
        return {"kept": False, "reason": "nothing_to_solve"}
    written = None
    for _ in range(ATTEMPTS):  # a walkthrough the guard throws out is asked for once more, then given up on
        try:
            written = learn.write_walkthrough(gateway, ctx, prepared)
        except LLMError as exc:
            return {"kept": False, "reason": f"llm_{exc.code}", "cost_usd": spent(ctx.request_id)}
        if written.content is not None:
            break
    assert written is not None
    with session_scope(user_id=None, role="system") as s:
        stored = learn.record_walkthrough(s, objective_id, written, actor=None, now=now)
    return {**written.checks, "kept": stored, "cost_usd": spent(ctx.request_id)}


def review(pairs: list[tuple[UUID, str]]) -> None:
    with session_scope(user_id=None, role="system") as s:
        for oid, code in pairs:
            row = s.scalar(select(Lesson).where(Lesson.objective_id == oid))
            walk = (row.content or {}).get("exam") if row else None
            if not walk:
                continue
            state = "shown" if walk.get("approved") else "waiting"
            print(f"\n[{state}] {code}  {walk['source_ref']}  -> {walk['final_answer']}")
            for step in walk["steps"]:
                print(f"   [{step['mark'] or '  '}] {step['text']}")
            if walk.get("tip"):
                print(f"   tip: {walk['tip']}")


def decide(pairs: list[tuple[UUID, str]], *, approved: bool) -> None:
    with session_scope(user_id=None, role="system") as s:
        done = [code for oid, code in pairs if learn.decide_walkthrough(s, oid, approved=approved, actor=None)]
    print(f"{'approved' if approved else 'rejected'} {len(done)}: {', '.join(done) or 'none stored'}")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.walkthroughs")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--only", help="objective codes, comma separated")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--redo", action="store_true", help="write again where one is stored (kept if it fails)")
    parser.add_argument("--run", action="store_true", help="make the calls; without it, print the estimate only")
    parser.add_argument("--review", action="store_true", help="print the stored walkthroughs; no calls")
    parser.add_argument("--approve", nargs="+", metavar="CODE", help="objective codes whose walkthrough she may see")
    parser.add_argument("--reject", nargs="+", metavar="CODE", help="objective codes whose walkthrough to delete")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args(argv[1:])

    if args.approve or args.reject:
        decide(objectives(args.subject, set(args.approve or args.reject)), approved=bool(args.approve))
        return
    only = {x.strip() for x in args.only.split(",")} if args.only else None
    pairs = objectives(args.subject, only)
    if args.review:
        review(pairs)
        return
    pending = todo(pairs, redo=args.redo)
    pending = pending[: args.limit] if args.limit else pending
    model = load_roles().role(learn.WALK_ROLE).model
    version = default_registry().get(learn.WALK_PROMPT).version
    print(
        f"{args.subject}: {len(pending)} walkthroughs to write, estimate "
        f"${len(pending) * COST_PER_WALKTHROUGH_USD:.3f} (model {model}, prompt {learn.WALK_PROMPT}/{version})",
        flush=True,
    )
    if not args.run or not pending:
        return
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
    if tenant_id is None:
        raise SystemExit("no household seeded (app.seed.household)")

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda p: {"code": p[1], **write_one(p[0], tenant_id)}, pending))

    reasons: dict[str, int] = {}
    for r in results:
        if not r.get("kept"):
            reasons[r.get("reason") or "not_stored"] = reasons.get(r.get("reason") or "not_stored", 0) + 1
    summary = {
        "subject": args.subject,
        "prompt": f"{learn.WALK_PROMPT}/{version}",
        "model": model,
        "tried": len(results),
        "kept": sum(bool(r.get("kept")) for r in results),
        "rejected": reasons,
        "cost_usd": round(sum(r.get("cost_usd") or 0 for r in results), 4),
        "per_topic": {r["code"]: (r.get("source_ref"), r.get("kept"), r.get("reason")) for r in results},
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"walkthroughs_{args.subject}_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"report: {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv)
