"""Add diagrams to lessons that are already written (docs/STUDENT-APP.md AC-U14).

The lesson text is never touched: this job asks only which picture, from the subject's own vocabulary, would
help — and supplies its numbers. Everything drawn is computed and checked by ``app.modules.learn.diagrams``
(SymPy, Pint), so a diagram that does not hold up is dropped rather than shown. The report counts what was kept
and what was dropped, and what it cost. No lesson text goes into the report.

A diagram is stored as a CANDIDATE. The checks prove its numbers, not that it teaches the right thing — a
transverse sine captioned "compressions and rarefactions" passes every check and is still wrong — so nothing is
shown to the student until a person approves it here.

Usage (from apps/api):
  uv run python -m app.jobs.illustrate --subject igcse-maths                  # estimate only, no calls
  uv run python -m app.jobs.illustrate --subject igcse-maths --limit 10 --run # illustrate the first 10
  uv run python -m app.jobs.illustrate --subject igcse-physics --redo --run   # go over illustrated ones again
  uv run python -m app.jobs.illustrate --subject igcse-maths --review         # list candidates, approved or not
  uv run python -m app.jobs.illustrate --subject igcse-maths --approve 6.1 8.4   # show these to her
  uv run python -m app.jobs.illustrate --subject igcse-maths --reject 3.3        # delete these candidates
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
from app.jobs import batching
from app.jobs.lessons import spent
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import BatchItem, CallContext, LLMError
from app.llm.prompts import default_registry
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.learn import lessons
from app.modules.learn import service as learn
from app.modules.learn.models import Lesson

REPORTS = API_ROOT.parents[1] / "evals" / "reports"
# One short call per lesson: the model returns a diagram choice and a handful of numbers, not prose.
COST_PER_LESSON_USD = 0.0004


def todo(subject_code: str, *, redo: bool, limit: int | None) -> tuple[UUID, list[UUID]]:
    """The subject, and its ready lessons that carry no diagram yet (or all of them, with ``redo``)."""
    prompt_version = default_registry().get(learn.ILLUSTRATE_PROMPT).version
    with session_scope(user_id=None, role="system") as s:
        subject_id = s.scalar(select(Subject.id).where(Subject.code == subject_code))
        if subject_id is None:
            raise SystemExit(f"unknown subject {subject_code}")
        rows = s.scalars(select(Lesson).where(Lesson.subject_id == subject_id, Lesson.status == "ready")).all()
        pending = [
            row.id for row in rows if redo or (row.checks or {}).get("diagram_prompt_version") not in (prompt_version,)
        ]
    return subject_id, pending[:limit] if limit else pending


def illustrate_one(lesson_id: UUID, subject_code: str) -> dict:
    gateway = build_gateway()
    now = datetime.now(UTC)
    request_id = f"illustrate:{lesson_id}:{now:%Y%m%d%H%M%S}"
    with session_scope(user_id=None, role="system") as s:
        row = s.get(Lesson, lesson_id)
        if row is None:
            return {"status": "missing"}
        ctx = CallContext(request_id=request_id, tenant_id=row.tenant_id)
        try:
            illustrated = learn.illustrate_lesson(s, gateway, ctx, row, subject_code=subject_code)
        except LLMError as exc:
            return {"status": "failed", "error": exc.code, "cost_usd": spent(request_id)}
        learn.record_diagrams(s, row, illustrated, actor=None, now=now)
    kept = illustrated.checks.get("kept", 0)
    return {
        "status": "illustrated" if kept else "no_diagram",
        **{k: v for k, v in illustrated.checks.items() if k != "cost_usd"},
        "cost_usd": spent(request_id),
    }


def illustrate_batch(pending: list[UUID], subject_code: str, *, resume: str | None = None) -> list[dict]:
    """Offer diagrams through the Batch API on the role's `:batch` model (user rule, 21 Sep 2026). The prompt, the
    subject's curated vocabulary and the checks are exactly those of the live path."""
    gateway = build_gateway()
    now = datetime.now(UTC)
    asks: dict[str, tuple[dict, set[str]]] = {}
    results: list[dict] = []
    tenant_id = None
    with session_scope(user_id=None, role="system") as s:
        for lesson_id in pending:
            row = s.get(Lesson, lesson_id)
            if row is None:
                continue
            tenant_id = row.tenant_id
            ask = learn.illustrate_lesson(s, None, None, row, subject_code=subject_code)
            if "variables" in ask.checks:
                asks[str(lesson_id)] = (ask.checks["variables"], set(ask.checks["allowed"]))
            else:
                results.append({"status": "no_diagram", **ask.checks})
    if not asks or tenant_id is None:
        return results
    got, failed, cost = batching.run(
        gateway,
        learn.ILLUSTRATE_ROLE,
        learn.ILLUSTRATE_PROMPT,
        [BatchItem(cid, variables) for cid, (variables, _) in asks.items()],
        lessons.DiagramDrafts,
        tenant_id,
        tag=f"illustrate-{subject_code}",
        resume=resume,
    )
    for cid, (_, allowed) in asks.items():
        if cid not in got:
            results.append({"status": "failed", "error": failed.get(cid, "missing")})
            continue
        with session_scope(user_id=None, role="system") as s:
            row = s.get(Lesson, UUID(cid))
            illustrated = learn.finish_illustration(row, got[cid], allowed=allowed)
            learn.record_diagrams(s, row, illustrated, actor=None, now=now)
        kept = illustrated.checks.get("kept", 0)
        results.append({"status": "illustrated" if kept else "no_diagram", **illustrated.checks})
    return results


def review(subject_code: str) -> None:
    """Every candidate diagram, with what it would draw, so a person can judge it."""
    with session_scope(user_id=None, role="system") as s:
        subject_id = s.scalar(select(Subject.id).where(Subject.code == subject_code))
        rows = s.scalars(select(Lesson).where(Lesson.subject_id == subject_id)).all()
        codes = {row.objective_id: curriculum.objective_detail(s, row.objective_id) for row in rows}
        for row in rows:
            detail = codes.get(row.objective_id)
            for index, diagram in enumerate((row.content or {}).get("diagrams", []), start=1):
                mark = "shown" if diagram.get("approved") else "waiting"
                name = f"{detail.code if detail else '?'}:{index}"
                print(f"[{mark:7}] {name:8} {diagram['kind']:15} {diagram['caption']}")
                print(f"{'':10} {json.dumps(diagram['data'])}")


def decide(subject_code: str, codes: list[str], *, approved: bool) -> None:
    """Approve (show) or reject (delete) candidates. "6.1" is every diagram on that objective, "6.1:2" the second."""
    wanted: dict[str, set[int] | None] = {}
    for code in codes:
        name, _, index = code.partition(":")
        if index:
            wanted.setdefault(name, set())
            picked = wanted[name]
            if picked is not None:
                picked.add(int(index))
        else:
            wanted[name] = None
    changed = 0
    with session_scope(user_id=None, role="system") as s:
        subject_id = s.scalar(select(Subject.id).where(Subject.code == subject_code))
        for row in s.scalars(select(Lesson).where(Lesson.subject_id == subject_id)).all():
            detail = curriculum.objective_detail(s, row.objective_id)
            if detail is None or detail.code not in wanted:
                continue
            content = dict(row.content or {})
            candidates = content.get("diagrams", [])
            if not candidates:
                continue
            picked = wanted[detail.code]
            chosen = [i for i, _ in enumerate(candidates, start=1) if picked is None or i in picked]
            if approved:
                content["diagrams"] = [
                    {**d, "approved": True} if i in chosen else d for i, d in enumerate(candidates, start=1)
                ]
            else:
                content["diagrams"] = [d for i, d in enumerate(candidates, start=1) if i not in chosen]
            row.content = content
            changed += len(chosen)
    print(f"{'approved' if approved else 'rejected'} {changed} diagram(s) on {', '.join(sorted(wanted))}")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.illustrate")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--redo", action="store_true", help="go over lessons that already carry a diagram")
    parser.add_argument("--run", action="store_true", help="make the calls; without it, print the estimate only")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--live", action="store_true", help="call the live model per lesson instead of the Batch API")
    parser.add_argument("--resume", metavar="BATCH_ID", help="collect a batch submitted by an interrupted run")
    parser.add_argument("--review", action="store_true", help="list candidate diagrams and what they draw")
    parser.add_argument("--approve", nargs="+", metavar="CODE", help="objective codes whose diagrams she may see")
    parser.add_argument("--reject", nargs="+", metavar="CODE", help="objective codes whose candidates to delete")
    args = parser.parse_args(argv[1:])

    if args.review:
        review(args.subject)
        return
    if args.approve or args.reject:
        if args.approve:
            decide(args.subject, args.approve, approved=True)
        if args.reject:
            decide(args.subject, args.reject, approved=False)
        return

    _, pending = todo(args.subject, redo=args.redo, limit=args.limit)
    role = load_roles().role(learn.ILLUSTRATE_ROLE)
    model = role.model if args.live else (role.batch_model or role.model)
    prompt = default_registry().get(learn.ILLUSTRATE_PROMPT)
    print(
        f"{args.subject}: {len(pending)} lessons to illustrate, estimate "
        f"${len(pending) * COST_PER_LESSON_USD:.2f} (model {model}, prompt {prompt.name}/{prompt.version})",
        flush=True,
    )
    if not args.run or not pending:
        return

    if args.live:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(lambda lesson_id: illustrate_one(lesson_id, args.subject), pending))
    else:
        results = illustrate_batch(pending, args.subject, resume=args.resume)

    kinds: dict[str, int] = {}
    with session_scope(user_id=None, role="system") as s:
        for row in s.scalars(select(Lesson).where(Lesson.id.in_(pending))):
            for diagram in (row.content or {}).get("diagrams", []):
                kinds[diagram["kind"]] = kinds.get(diagram["kind"], 0) + 1
    report = {
        "subject": args.subject,
        "prompt": f"{prompt.name}/{prompt.version}",
        "model": model,
        "lessons": len(results),
        "with_diagram": sum(1 for r in results if r["status"] == "illustrated"),
        "no_diagram": sum(1 for r in results if r["status"] == "no_diagram"),
        "no_vocabulary": sum(1 for r in results if r.get("skipped") == "no vocabulary"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "kinds": kinds,
        "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in results), 4),
        "dropped_kind": sum(r.get("dropped_kind", 0) for r in results),
        "dropped_numbers": sum(r.get("dropped_numbers", 0) for r in results),
        "dropped_caption": sum(r.get("dropped_caption", 0) for r in results),
        "dropped_uncited": sum(r.get("dropped_uncited", 0) for r in results),
        "dropped_ungrounded": sum(r.get("dropped_ungrounded", 0) for r in results),
        "errors": sorted({r["error"] for r in results if r.get("error")}),
    }
    print(json.dumps(report, indent=2), flush=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"illustrate_{args.subject}_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv)
