"""Write topic lessons ahead of time, and report how the guard treated them (docs/STUDENT-APP.md, AC-U3–U6).

A lesson is otherwise written the first time she opens a topic. This job writes them in bulk so pages open at
once, rewrites lessons whose prompt, guard or model is out of date (in place: a rewrite that fails or comes back
empty keeps the old lesson), and doubles as the lesson eval: its report counts how many lessons were grounded,
how many sections and worked examples the guard removed, and what it cost.
No lesson text goes into the report.

Usage (from apps/api):
  uv run python -m app.jobs.lessons --subject igcse-maths                 # estimate only, no calls
  uv run python -m app.jobs.lessons --subject igcse-maths --limit 10 --run  # write the first 10 missing
  uv run python -m app.jobs.lessons --subject igcse-sociology --stale --run # rewrite out-of-date lessons too
  uv run python -m app.jobs.lessons --subject igcse-maths --stale-only --run # only rewrite out-of-date ones
  uv run python -m app.jobs.lessons --subject igcse-sociology --recheck     # apply a stricter guard, no calls
  uv run python -m app.jobs.lessons --subject igcse-maths --pilot 1.1,15.4 --prompt-version v4 --run
      # write with another prompt (or --model) beside the stored lessons, for a person to compare; saves nothing
      # to the database. Its output holds lesson text, so it goes to evals/runs/ (not committed).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import session_scope
from app.jobs import batching
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import BatchItem, CallContext, LLMError
from app.llm.models import LlmCall
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import LearningObjective, Subject
from app.modules.identity.models import Tenant
from app.modules.learn import lessons
from app.modules.learn import service as learn
from app.modules.learn.models import Lesson

REPORTS = API_ROOT.parents[1] / "evals" / "reports"
RUNS = API_ROOT.parents[1] / "evals" / "runs"
# Measured 19 Sep 2026 on gemini-2.5-flash-lite (llm_call): $0.015 for 10 lessons, one of which looped to the cap
# and was retried. Rounded up for retries. (gemini-3.5-flash, used for the first 29, cost ~$0.07 each.)
# z-ai/glm-5.3-flash:batch at $0.075/M in, $0.25/M out: ~6k tokens in and ~3k out per v4 lesson, rounded up.
COST_PER_LESSON_USD = 0.002


def todo(subject_code: str, *, stale: bool, limit: int | None, missing: bool = True) -> list[UUID]:
    """Objectives with no lesson (unless ``missing`` is off), plus (with ``stale``) out-of-date ones."""
    prompt_version = learn.LESSON_PROMPT_VERSION
    with session_scope(user_id=None, role="system") as s:
        subject = s.scalar(select(Subject).where(Subject.code == subject_code))
        if subject is None:
            raise SystemExit(f"unknown subject {subject_code}")
        tree = curriculum.subject_tree(s, subject.id)
        objective_ids = learn.objective_ids(tree.topics) if tree else []
        stored = {
            row.objective_id: row for row in s.scalars(select(Lesson).where(Lesson.objective_id.in_(objective_ids)))
        }

    model = load_roles().role(learn.LESSON_ROLE).model

    def out_of_date(row: Lesson) -> bool:
        """Written by an older prompt, an older guard, or a model the role no longer names."""
        return (
            row.prompt_version not in (None, prompt_version)
            or row.guard_version != lessons.GUARD_VERSION
            or (row.model is not None and row.model != model)
        )

    pending = [
        oid
        for oid in objective_ids
        if (missing and oid not in stored) or (stale and oid in stored and out_of_date(stored[oid]))
    ]
    return pending[:limit] if limit else pending


def by_code(subject_code: str, codes: set[str]) -> list[UUID]:
    """The subject's objectives with these codes, in syllabus order."""
    with session_scope(user_id=None, role="system") as s:
        subject = s.scalar(select(Subject).where(Subject.code == subject_code))
        if subject is None:
            raise SystemExit(f"unknown subject {subject_code}")
        tree = curriculum.subject_tree(s, subject.id)
        wanted = learn.objective_ids(tree.topics) if tree else []
        found = dict(
            s.execute(
                select(LearningObjective.id, LearningObjective.code).where(LearningObjective.id.in_(wanted))
            ).all()
        )
    return [oid for oid in wanted if found.get(oid) in codes]


def spent(request_id: str) -> float:
    """What every call under one request cost, schema-repair retries included (``llm_call`` is the record;
    a model result reports only its own final call)."""
    with session_scope(user_id=None, role="system") as s:
        total = s.scalar(select(func.sum(LlmCall.cost_usd)).where(LlmCall.request_id == request_id))
    return float(total or 0.0)


def write_one(objective_id: UUID, tenant_id: UUID, *, rewrite: bool) -> dict:
    gateway = build_gateway()
    now = datetime.now(UTC)
    ctx = CallContext(request_id=f"lesson:{objective_id}:{now:%Y%m%d%H%M%S}", tenant_id=tenant_id)
    with session_scope(user_id=None, role="system") as s:
        prepared = learn.prepare_lesson(s, gateway, ctx, objective_id, rewrite=rewrite)
        if not isinstance(prepared, learn.PreparedLesson):
            return {"status": prepared.status, "skipped": True}
    try:
        written = learn.write_lesson(gateway, ctx, prepared)
        if written.status != "ready" and learn.needs_writing(prepared):
            written = learn.write_lesson(gateway, ctx, prepared)
    except LLMError as exc:
        return {"status": "failed", "error": exc.code, "cost_usd": spent(ctx.request_id)}
    if rewrite and written.status != "ready":
        # Never swap a lesson she can read for a blank one: the old one stays and the topic is listed for a retry.
        return {"status": "kept_old", **written.checks, "cost_usd": spent(ctx.request_id)}
    with session_scope(user_id=None, role="system") as s:
        learn.record_lesson(s, prepared, written, actor=None, now=now)
    return {"status": written.status, **written.checks, "cost_usd": spent(ctx.request_id)}


def pilot(subject_code: str, codes: list[str], *, prompt_version: str, models: list[str] | None) -> dict:
    """Write lessons for a few objectives with another prompt or model, next to the stored ones. Nothing is
    stored: a person compares them first (docs/STUDENT-APP.md §15)."""
    gateway = build_gateway()
    now = datetime.now(UTC)
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        subject = s.scalar(select(Subject).where(Subject.code == subject_code))
        if subject is None or tenant_id is None:
            raise SystemExit(f"unknown subject {subject_code} or no household")
        tree = curriculum.subject_tree(s, subject.id)
        by_code = {o.code: o for o in _objectives(tree.topics if tree else [])}
    out: dict = {"subject": subject_code, "prompt_version": prompt_version, "models": models, "topics": []}
    for code in codes:
        objective = by_code.get(code)
        if objective is None:
            out["topics"].append({"code": code, "error": "unknown objective"})
            continue
        ctx = CallContext(request_id=f"lesson-pilot:{objective.id}:{now:%Y%m%d%H%M%S}", tenant_id=tenant_id)
        with session_scope(user_id=None, role="system") as s:
            stored = s.scalar(select(Lesson).where(Lesson.objective_id == objective.id))
            old = dict(stored.content or {}) if stored else {}
            old_meta = {"model": stored.model, "prompt": stored.prompt_version} if stored else {}
            prepared = learn.prepare_lesson(s, gateway, ctx, objective.id, rewrite=True)
        assert isinstance(prepared, learn.PreparedLesson)
        try:
            written = learn.write_lesson(gateway, ctx, prepared, prompt_version=prompt_version, models=models)
        except LLMError as exc:
            out["topics"].append({"code": code, "statement": objective.statement, "error": exc.code})
            continue
        out["topics"].append(
            {
                "code": code,
                "statement": objective.statement,
                "examined": prepared.variables.get("examined", ""),
                "old": old,
                "old_meta": old_meta,
                "new": written.content,
                "new_meta": {"model": written.model, "prompt": written.prompt_version, "status": written.status},
                "checks": written.checks,
                "cost_usd": spent(ctx.request_id),
            }
        )
    RUNS.mkdir(parents=True, exist_ok=True)
    tag = (models[0].split("/")[-1] if models else "role-model").replace(":", "-")
    path = RUNS / f"lesson_pilot_{subject_code}_{prompt_version}_{tag}_{now:%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    out["path"] = str(path)
    return out


def _objectives(nodes):  # type: ignore[no-untyped-def]
    for node in nodes:
        yield from node.objectives
        yield from _objectives(node.children)


def _store(prepared: learn.PreparedLesson, written: learn.WrittenLesson, *, rewrite: bool, now: datetime) -> dict:
    if rewrite and written.status != "ready":
        # Never swap a lesson she can read for a blank one: the old one stays and the topic is listed for a retry.
        return {"status": "kept_old", **written.checks}
    with session_scope(user_id=None, role="system") as s:
        learn.record_lesson(s, prepared, written, actor=None, now=now)
    return {"status": written.status, **written.checks}


def write_batch(
    pending: list[UUID], tenant_id: UUID, *, rewrite: bool, subject: str, resume: str | None = None
) -> tuple[list[dict], float]:
    """Write lessons through the Batch API on the role's `:batch` model (user rule, 21 Sep 2026). Retrieval and
    the guard are exactly those of a live lesson; only the model call is queued."""
    gateway = build_gateway()
    now = datetime.now(UTC)
    ctx = CallContext(request_id=f"lesson-batch-prep:{now:%Y%m%d%H%M%S}", tenant_id=tenant_id)
    prepared: dict[str, learn.PreparedLesson] = {}
    results: list[dict] = []
    for oid in pending:
        with session_scope(user_id=None, role="system") as s:
            p = learn.prepare_lesson(s, gateway, ctx, oid, rewrite=rewrite)
        if not isinstance(p, learn.PreparedLesson):
            results.append({"status": p.status, "skipped": True})
        elif not learn.needs_writing(p):
            thin = learn.WrittenLesson("not_enough_material", {}, {"retrieval_state": p.retrieval_state}, None, None)
            results.append(_store(p, thin, rewrite=rewrite, now=now))
        else:
            prepared[str(oid)] = p
    if not prepared:
        return results, 0.0
    got, failed, cost = batching.run(
        gateway,
        learn.LESSON_ROLE,
        learn.LESSON_PROMPT,
        [BatchItem(cid, p.variables) for cid, p in prepared.items()],
        lessons.LessonDraft,
        tenant_id,
        tag=f"lessons-{subject}",
        prompt_version=learn.LESSON_PROMPT_VERSION,
        resume=resume,
    )
    for cid, p in prepared.items():
        if cid in got:
            results.append(_store(p, learn.finish_lesson(p, got[cid]), rewrite=rewrite, now=now))
        else:
            results.append({"status": "failed", "error": failed.get(cid, "missing")})
    return results, cost


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.lessons")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--stale",
        action="store_true",
        help="also rewrite lessons from an older prompt, guard or model (replaced in place)",
    )
    parser.add_argument("--stale-only", action="store_true", help="rewrite out-of-date lessons; write no new ones")
    parser.add_argument("--only", help="objective codes to (re)write, comma separated, stored or not")
    parser.add_argument("--run", action="store_true", help="make the calls; without it, print the estimate only")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--live", action="store_true", help="call the live model one lesson at a time instead of the Batch API"
    )
    parser.add_argument("--resume", metavar="BATCH_ID", help="collect a batch submitted by an interrupted run")
    parser.add_argument("--recheck", action="store_true", help="apply the current guard to stored lessons; no LLM")
    parser.add_argument("--pilot", help="objective codes to write beside the stored lessons; nothing is saved")
    parser.add_argument("--prompt-version", default=learn.LESSON_PROMPT_VERSION, help="with --pilot: e.g. v4")
    parser.add_argument("--model", help="with --pilot: screen another model (ask before anything pricier)")
    args = parser.parse_args(argv[1:])

    if args.pilot:
        codes = [c.strip() for c in args.pilot.split(",") if c.strip()]
        # The user's rule (21 Sep 2026): the pilot may compare only the two allowed live models.
        allowed = {"google/gemini-2.5-flash-lite", "z-ai/glm-5.3-flash"}
        if args.model and args.model not in allowed:
            raise SystemExit(f"--model must be one of {sorted(allowed)} (user rule, 21 Sep 2026)")
        models = [args.model] if args.model else None
        print(
            f"{args.subject}: pilot of {len(codes)} lessons, prompt {args.prompt_version}, "
            f"model {args.model or load_roles().role(learn.LESSON_ROLE).model}",
            flush=True,
        )
        if not args.run:
            return
        result = pilot(args.subject, codes, prompt_version=args.prompt_version, models=models)
        for topic in result["topics"]:
            checks = topic.get("checks", {})
            print(
                f"{topic['code']}: {topic.get('new_meta', {}).get('status', topic.get('error'))} "
                f"sections {checks.get('kept_sections')} examples {checks.get('kept_examples')} "
                f"(dropped wrong {checks.get('dropped_examples_wrong')}, past paper "
                f"{checks.get('dropped_examples_past_paper')}) ${topic.get('cost_usd', 0):.4f}",
                flush=True,
            )
        print(f"output: {result['path']}", flush=True)
        return

    if args.recheck:
        with session_scope(user_id=None, role="system") as s:
            subject_id = s.scalar(select(Subject.id).where(Subject.code == args.subject))
            if subject_id is None:
                raise SystemExit(f"unknown subject {args.subject}")
            print(f"{args.subject}: {learn.recheck_stored(s, subject_id)} (guard {lessons.GUARD_VERSION})", flush=True)
        return

    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))  # the household (product for one)
    stale = args.stale or args.stale_only or bool(args.only)
    if args.only:
        # Chosen topics are rewritten whatever they hold; a failed rewrite keeps the old lesson (write_one).
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        pending = by_code(args.subject, wanted)
    else:
        pending = todo(args.subject, stale=stale, limit=args.limit, missing=not args.stale_only)
    role = load_roles().role(learn.LESSON_ROLE)
    model = role.model if args.live else (role.batch_model or role.model)
    print(
        f"{args.subject}: {len(pending)} lessons to write, estimate ${len(pending) * COST_PER_LESSON_USD:.2f} "
        f"(model {model}, prompt {learn.LESSON_PROMPT}/{learn.LESSON_PROMPT_VERSION})",
        flush=True,
    )
    if not args.run or not pending:
        return
    if tenant_id is None:
        raise SystemExit("no household seeded (app.seed.household)")

    batch_cost: float | None = None
    if args.live:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(lambda oid: write_one(oid, tenant_id, rewrite=stale), pending))
    else:
        results, batch_cost = write_batch(pending, tenant_id, rewrite=stale, subject=args.subject, resume=args.resume)

    counted = [r for r in results if not r.get("skipped")]
    summary: dict = {
        "subject": args.subject,
        "prompt": f"{learn.LESSON_PROMPT}/{learn.LESSON_PROMPT_VERSION}",
        "guard": lessons.GUARD_VERSION,
        "model": model,
        "lessons": len(counted),
        "ready": sum(r["status"] == "ready" for r in counted),
        "not_enough_material": sum(r["status"] == "not_enough_material" for r in counted),
        "failed": sum(r["status"] == "failed" for r in counted),
        "kept_old": sum(r["status"] == "kept_old" for r in counted),
        "errors": sorted({r["error"] for r in counted if r.get("error")}),
        # from llm_call, retries included (live); the batch's own reported cost (batch)
        "cost_usd": round(batch_cost if batch_cost is not None else sum(r.get("cost_usd") or 0 for r in counted), 4),
    }
    for key in lessons.GuardReport().as_dict():
        summary[key] = sum(r.get(key, 0) for r in counted)
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"lessons_{args.subject}_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"report: {path}", flush=True)


if __name__ == "__main__":
    main(sys.argv)
