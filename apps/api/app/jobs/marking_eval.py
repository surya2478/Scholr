"""Screen a marking role on deterministic scripts built from verified past-paper items. Nothing is saved.

Each script uses a different verified numeric item (exact value, no diagram), spread across papers, rotating through:
- correct: a correct final answer (Cambridge accuracy), no working — gold: full marks;
- correct_working: the same with a one-line method — gold: full marks;
- wrong: a clearly wrong final answer, no working — gold: 0.
Reports tool agreement, unsafe finals and the AC-E4 measure (total marks within 1 of gold on >= 90% of 40 scripts).
The gold marks are synthetic: AC-E4 is only fully met on teacher-marked scripts (CONTEXT U3).

Usage (from apps/api):
  uv run python -m app.jobs.marking_eval --subject igcse-maths [--role maths_marker] [--scripts 40]         # estimate
  uv run python -m app.jobs.marking_eval --subject igcse-maths [--role maths_marker] [--scripts 40] --run   # calls
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sympy
from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import session_scope
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext, LLMError
from app.modules.assessment.models import QuestionItem
from app.modules.curriculum.models import Subject
from app.modules.evaluation.structured_math import MathInput, evaluate
from app.modules.subjects.service import taught_config_for
from app.tools.answer_check import check_final_answer
from app.tools.math_sympy import MathParseError, parse_math, round_sig

REPORTS_DIR = API_ROOT.parents[1] / "evals" / "reports"
# Pass = no wrong result marked final; few errors; the review queue stays manageable.
PASS = {"unsafe_final_max": 0, "error_rate_max": 0.05, "review_rate_max": 0.25, "tool_agreement_min": 0.9}
AC_E4 = {"scripts_min": 40, "within_one_of_gold_min": 0.9}
KINDS = ("correct", "correct_working", "wrong")
COST_PER_CALL_USD = 0.0004  # Flash-Lite marker: screen mean $0.00025 per call, with a retry margin


@dataclass(frozen=True)
class Case:
    tenant_id: UUID
    source_ref: str
    kind: str  # one of KINDS
    answer: str
    gold: int
    inp: MathInput


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f") if value == value.to_integral() else format(value, "f")


def build_cases(item: QuestionItem, base: dict[str, Any]) -> list[Case]:
    spec = dict(item.answer_spec)
    try:
        exact = Decimal(str(sympy.N(parse_math(spec["exact"], rational=True), 30)))
    except (MathParseError, TypeError, ValueError, ArithmeticError):
        return []
    correct = next(
        (
            candidate
            for candidate in (_plain(round_sig(exact, n)) for n in (3, 4, 5, 6))
            if check_final_answer(candidate, spec, command_word=item.command_word).status == "correct"
        ),
        None,
    )
    wrong = _plain(round_sig(exact * Decimal("1.37") + 1, 3))
    if check_final_answer(wrong, spec, command_word=item.command_word).status != "incorrect":
        wrong = None
    cases = []
    for kind, answer, working, gold in (
        ("correct", correct, None, item.marks),
        ("correct_working", correct, f"{spec['exact']} = {correct}", item.marks),
        ("wrong", wrong, None, 0),
    ):
        if answer is None:
            continue
        inp = MathInput(
            marks=item.marks,
            stem=item.stem,
            context=item.context,
            command_word=item.command_word,
            answer_spec=spec,
            mark_scheme=str((item.mark_scheme or {}).get("text", "")),
            working=working,
            final_answer=answer,
            **base,
        )
        cases.append(Case(item.tenant_id, item.source_ref or str(item.id), kind, answer, gold, inp))
    return cases


def choose_scripts(options_per_item: list[list[Case]], count: int) -> list[Case]:
    """One script per item, rotating kinds so the benchmark is balanced; falls back to what an item allows."""
    scripts: list[Case] = []
    for options in options_per_item:
        if not options:
            continue
        wanted = KINDS[len(scripts) % len(KINDS)]
        scripts.append(next((c for c in options if c.kind == wanted), options[0]))
        if len(scripts) == count:
            break
    return scripts


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.marking_eval")
    parser.add_argument("--subject", default="igcse-maths")
    parser.add_argument("--role")
    parser.add_argument("--scripts", type=int, default=AC_E4["scripts_min"])
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--run", action="store_true", help="make the calls (otherwise print the estimate)")
    args = parser.parse_args(argv[1:])

    config = taught_config_for(args.subject)
    role = args.role or config.evaluation.evaluator_role
    model = load_roles().role(role).model
    base = {
        "from_photo": False,
        "evaluator_role": role,
        "confidence_threshold": config.evaluation.confidence_threshold,
        "mistake_categories": tuple(config.mistake_categories),
        "mistake_labels": tuple(config.common_mistakes),
    }
    with session_scope(user_id=None, role="system") as s:
        subject_id = s.scalar(select(Subject.id).where(Subject.code == args.subject))
        items = [
            item
            for item in s.scalars(
                select(QuestionItem)
                .where(
                    QuestionItem.subject_id == subject_id,
                    QuestionItem.verification_status == "verified",
                    QuestionItem.has_diagram.is_(False),
                )
                .order_by(QuestionItem.source_ref)
            )
            if item.answer_spec.get("type") == "numeric" and item.answer_spec.get("exact")
        ]
        items.sort(key=lambda item: zlib.crc32((item.source_ref or str(item.id)).encode()))  # spread across papers
        cases = choose_scripts([build_cases(item, base) for item in items], args.scripts)
    if not cases:
        raise SystemExit("no verified numeric items with exact values to build cases from")
    if not args.run:
        print(
            f"{len(cases)} scripts ({dict(Counter(c.kind for c in cases))}) -> {len(cases)} calls to {role} ({model}). "
            f"Estimated cost ~ ${len(cases) * COST_PER_CALL_USD:.3f}. Re-run with --run."
        )
        return

    gateway = build_gateway()

    def run(case: Case) -> dict[str, Any]:
        row: dict[str, Any] = {"source_ref": case.source_ref, "case": case.kind, "gold": case.gold}
        try:
            out = evaluate(gateway, CallContext(request_id=f"marking_eval:{role}", tenant_id=case.tenant_id), case.inp)
        except LLMError as exc:
            return {**row, "error": exc.code}
        return {
            **row,
            "tool": out.tool.status,
            "agreement": out.tool_agreement,
            "marks": out.marks_awarded,
            "available": out.marks_available,
            "status": out.status,
            "confidence": out.confidence,
            "issues": out.issues,
            "cost_usd": out.cost_usd or 0.0,
        }

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows = list(pool.map(run, cases))

    done = [r for r in rows if "error" not in r]
    correct = [r for r in done if r["case"] != "wrong"]
    wrong = [r for r in done if r["case"] == "wrong"]
    decisive = [r for r in done if r["agreement"] != "not_applicable"]

    def rate(part: list[dict[str, Any]], whole: list[dict[str, Any]]) -> float | None:
        return round(len(part) / len(whole), 3) if whole else None

    # A wrong result that is still marked final is what would reach the student and mastery unchecked.
    unsafe_final = [
        r
        for r in done
        if r["status"] == "final"
        and ((r["case"] != "wrong" and r["marks"] < r["available"]) or (r["case"] == "wrong" and r["marks"] > 0))
    ]
    within_one = rate([r for r in done if abs(r["marks"] - r["gold"]) <= 1], rows)  # errors count as misses
    summary = {
        "calls": len(rows),
        "errors": dict(Counter(r["error"] for r in rows if "error" in r)),
        "error_rate": rate([r for r in rows if "error" in r], rows),
        "unsafe_final": len(unsafe_final),
        "review_rate": rate([r for r in done if r["status"] != "final"], done),
        "tool_agreement": rate([r for r in decisive if r["agreement"] == "agree"], decisive),
        "full_marks_when_correct": rate([r for r in correct if r["marks"] == r["available"]], correct),
        "zero_marks_when_wrong": rate([r for r in wrong if r["marks"] == 0], wrong),
        "mean_cost_usd": round(sum(r["cost_usd"] for r in done) / len(done), 5) if done else None,
        "ac_e4_synthetic": {
            "scripts": len(rows),
            "within_one_of_gold": within_one,
            "met": len(rows) >= AC_E4["scripts_min"] and (within_one or 0) >= AC_E4["within_one_of_gold_min"],
            "note": "synthetic gold; teacher-marked scripts (U3) are still needed for AC-E4",
        },
    }
    ok = (
        bool(done)
        and summary["unsafe_final"] <= PASS["unsafe_final_max"]
        and summary["error_rate"] <= PASS["error_rate_max"]  # type: ignore[operator]
        and summary["review_rate"] <= PASS["review_rate_max"]  # type: ignore[operator]
        and (summary["tool_agreement"] or 0) >= PASS["tool_agreement_min"]  # type: ignore[operator]
    )
    summary["verdict"] = "candidate_ok" if ok else "review"

    for r in rows:
        print(
            f"  {r['source_ref']:22} {r['case']:15} gold={r['gold']} "
            + (
                f"error={r['error']}"
                if "error" in r
                else f"tool={r['tool']:22} agree={r['agreement']:14} marks={r['marks']}/{r['available']} "
                f"status={r['status']:12} conf={r['confidence']} issues={r['issues']}"
            ),
            flush=True,
        )
    print(f"\nrole={role} model={model}\n{json.dumps(summary, indent=2)}")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"marking_{args.subject}_{role}_{model.replace('/', '_')}_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(
        json.dumps({"role": role, "model": model, "pass_thresholds": PASS, "summary": summary, "rows": rows}, indent=2),
        encoding="utf-8",
    )
    print(f"report: {path}")


if __name__ == "__main__":
    main(sys.argv)
