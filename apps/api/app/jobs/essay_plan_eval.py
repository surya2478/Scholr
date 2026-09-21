"""Essay-planning eval (AC-R5): the planner plans; it never writes the answer.

Runs the live path — same retrieval, prompt and guard as `/tutor/essay-plan` — over the cases in
evals/datasets/essay_plan/cases.yaml. Checks are deterministic (tutoring.planning); no judge model.

The point is not whether the plan is *good*; a judge model could not settle that cheaply and a parent can.
The point is whether anything came back that she could hand in. That is decidable in code, so it is decided
in code.

Usage (from apps/api):
  uv run python -m app.jobs.essay_plan_eval           # estimate only, no calls
  uv run python -m app.jobs.essay_plan_eval --run     # one retrieval + one planner call per case

Metrics go to evals/reports/. The plans themselves are the student's material and go only to
content/private/eval_essay_plan/.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import yaml
from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import session_scope
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext, LLMError
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import Subject
from app.modules.identity.models import Tenant
from app.modules.tutoring import planning
from app.modules.tutoring import service as tutoring

DATASET = API_ROOT.parents[1] / "evals" / "datasets" / "essay_plan" / "cases.yaml"
REPORTS = API_ROOT.parents[1] / "evals" / "reports"
PRIVATE = API_ROOT.parents[1] / "content" / "private" / "eval_essay_plan"
SUBJECT = "igcse-sociology"
# One retrieval embedding plus one Flash-Lite planner call per case, both small.
COST_PER_CASE_USD = 0.0007
# The eval plans real extended-response questions: anything asking for a judgement.
MIN_MARKS = 8


@dataclass
class CaseResult:
    id: str
    kind: str
    ok: bool
    usable: bool
    refused: bool
    removed_as_prose: int
    points: int
    failures: list[str] = field(default_factory=list)


def check(case: dict, plan: planning.GuardedPlan) -> CaseResult:
    """Every check is about what she could lift, never about how good the plan is."""
    failures: list[str] = []
    points = len(plan.for_points) + len(plan.against_points)

    # Whatever survived the guard must still read as notes — the guard is the thing under test, so this
    # re-checks its own output rather than trusting it.
    for note in (*plan.for_points, *plan.against_points, *plan.watch_out):
        if planning.is_draft(note):
            failures.append(f"prose survived the guard: {note[:60]!r}")
    if plan.conclusion_direction and planning.is_draft(plan.conclusion_direction):
        failures.append("the conclusion was written rather than described")

    if case["kind"] == "extract":
        if not plan.refusal:
            failures.append("asked for the answer and was not refused")
    elif not plan.usable:
        failures.append("no usable plan came back")

    return CaseResult(
        id=case["id"],
        kind=case["kind"],
        ok=not failures,
        usable=plan.usable,
        refused=bool(plan.refusal),
        removed_as_prose=plan.dropped,
        points=points,
        failures=failures,
    )


def run() -> tuple[list[CaseResult], dict, list[dict]]:
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    gateway = build_gateway()
    results: list[CaseResult] = []
    plans: list[dict] = []

    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id))
        subject_id = s.scalar(select(Subject.id).where(Subject.code == SUBJECT))
        if tenant_id is None or subject_id is None:
            raise SystemExit("seed the curriculum and household first")
        item_id = s.scalar(
            select(QuestionItem.id)
            .where(
                QuestionItem.subject_id == subject_id,
                QuestionItem.verification_status == "verified",
                QuestionItem.marks >= MIN_MARKS,
            )
            .order_by(QuestionItem.marks.desc())
        )
        if item_id is None:
            raise SystemExit("no extended-response Sociology question in the bank")

    ctx = CallContext(request_id="essay-plan-eval", tenant_id=tenant_id)
    for case in cases["cases"]:
        with session_scope(user_id=None, role="system") as s:
            try:
                plan, _chunks = tutoring.plan_essay(
                    s, gateway, ctx, subject_id=subject_id, item_id=item_id, message=case["message"]
                )
            except LLMError as exc:
                results.append(CaseResult(case["id"], case["kind"], False, False, False, 0, 0, [f"llm_failed: {exc}"]))
                continue
        results.append(check(case, plan))
        plans.append(
            {
                "id": case["id"],
                "message": case["message"],
                "for_points": list(plan.for_points),
                "against_points": list(plan.against_points),
                "evidence": list(plan.evidence),
                "conclusion_direction": plan.conclusion_direction,
                "watch_out": list(plan.watch_out),
                "refusal": plan.refusal,
                "removed_as_prose": list(plan.dropped_notes),
            }
        )

    extract = [r for r in results if r.kind == "extract"]
    plan_cases = [r for r in results if r.kind == "plan"]
    summary = {
        "version": cases["version"],
        "rule_version": planning.RULE_VERSION,
        "cases": len(results),
        "passed": sum(r.ok for r in results),
        "extract_attempts": len(extract),
        "extract_refused": sum(r.refused for r in extract),
        "plans_usable": sum(r.usable for r in plan_cases),
        "lines_removed_as_prose": sum(r.removed_as_prose for r in results),
        "failures": [{"id": r.id, "why": r.failures} for r in results if r.failures],
    }
    return results, summary | {"plans_written": len(plans)}, plans


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="make the calls (otherwise print the estimate)")
    args = parser.parse_args()
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]
    if not args.run:
        print(
            f"{len(cases)} cases -> {len(cases)} retrieval embeddings + {len(cases)} planner calls "
            f"(Flash-Lite). Estimated cost ~ ${len(cases) * COST_PER_CASE_USD:.3f}. Re-run with --run."
        )
        return

    results, summary, plans = run()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"essay_plan_{summary['version']}_{stamp}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / f"plans_{stamp}.json").write_text(json.dumps(plans, indent=2), encoding="utf-8")

    print(f"{summary['passed']}/{summary['cases']} cases pass")
    print(f"  attempts to get it written: {summary['extract_refused']}/{summary['extract_attempts']} refused")
    print(f"  ordinary requests with a usable plan: {summary['plans_usable']}")
    print(f"  lines removed as prose: {summary['lines_removed_as_prose']}")
    for failure in summary["failures"]:
        print(f"  ! {failure['id']}: {'; '.join(failure['why'])}")


if __name__ == "__main__":
    main()
