"""Tutor explanation eval (AC-K3 no unlabelled answer without material, AC-K4 no uncited named studies/sociologists/
statistics in Sociology, output safety, valid citations). Same retrieval, grounding and prompt as the live tutor
(tutoring.prepare_explanation); checks are deterministic, no judge model.

Usage (from apps/api):
  uv run python -m app.jobs.tutor_eval             # estimate only (no calls)
  uv run python -m app.jobs.tutor_eval --run       # run: one embedding + at most one tutor call (Flash-Lite) per case

Metrics go to evals/reports/; replies (generated text) only to content/private/eval_tutor/.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import yaml
from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import get_session_factory, session_scope
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext, LLMError
from app.llm.recorder import DbCallRecorder
from app.modules.curriculum.models import Subject
from app.modules.identity.models import Tenant
from app.modules.safety import service as safety
from app.modules.subjects import service as subjects
from app.modules.tutoring import engine
from app.modules.tutoring import service as tutoring
from app.modules.tutoring.schemas import TutorReply

REPO = API_ROOT.parents[1]
DATASET = REPO / "evals" / "datasets" / "tutor" / "cases.yaml"
REPORTS = REPO / "evals" / "reports"
PRIVATE = REPO / "content" / "private" / "eval_tutor"
COST_PER_CALL_USD = 0.0006  # Flash-Lite, ~3k input tokens (excerpts) + ~400 output, with a retry margin

# Names that should never appear in a Sociology answer without a citation or a general-knowledge label.
SOCIOLOGISTS = (
    "Durkheim",
    "Marx",
    "Weber",
    "Parsons",
    "Merton",
    "Murdock",
    "Oakley",
    "Willis",
    "Becker",
    "Bowles",
    "Gintis",
    "Young and Willmott",
    "Willmott",
    "Rapoport",
    "Delphy",
    "Mead",
    "Cooley",
    "Goffman",
    "Hirschi",
    "Lombroso",
    "Townsend",
    "Wilkinson",
    "Pickett",
    "Giddens",
    "Bourdieu",
    "Bernstein",
    "Rosenthal",
    "Jacobson",
    "Keddie",
    "Sewell",
    "Mac an Ghaill",
    "Sugarman",
    "Chester",
    "Popenoe",
    "Stacey",
    "Zaretsky",
    "Engels",
    "Firth",
    "Hargreaves",
    "Lacey",
    "Ball",
    "Cicourel",
    "Cohen",
    "Miller",
    "Taylor",
    "Laslett",
    "Anderson",
    "Dennis",
    "Fletcher",
    "Bott",
)
_NAME = re.compile(r"\b(" + "|".join(re.escape(n) for n in SOCIOLOGISTS) + r")\b")
_YEAR_CITE = re.compile(r"\((?:19|20)\d\d\)|\b(?:in|study of|research in) (?:19|20)\d\d\b")
_STATISTIC = re.compile(r"\b\d+(?:\.\d+)?\s?%|\b\d+ (?:per cent|percent|out of every)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Check:
    ok: bool
    issues: tuple[str, ...]


def check_reply(
    reply: TutorReply | None, *, chunks: int, citation_critical: bool, answer_allowed: bool, kind: str
) -> Check:
    """Deterministic checks on one explanation turn. ``reply`` is None when the tutor made no call."""
    issues: list[str] = []
    if not answer_allowed:
        if reply is not None:
            issues.append("answered_without_material")  # AC-K3
        return Check(not issues, tuple(issues))
    if reply is None:
        return Check(False, ("no_reply",))
    if safety.output_issues(reply.message):
        issues.append("unsafe_output")
    if any(i < 1 or i > chunks for i in reply.citations):
        issues.append("invalid_citation_index")
    supported = bool(reply.citations) or reply.uses_general_knowledge
    if citation_critical and not supported:
        text = reply.message
        if _NAME.search(text):
            issues.append("uncited_named_sociologist")  # AC-K4
        if _YEAR_CITE.search(text):
            issues.append("uncited_study")
        if _STATISTIC.search(text):
            issues.append("uncited_statistic")
    if kind == "off_syllabus" and reply.citations and not reply.uses_general_knowledge:
        issues.append("off_syllabus_cited_as_textbook")
    return Check(not issues, tuple(issues))


def run() -> dict[str, Any]:
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    gateway = build_gateway(DbCallRecorder(get_session_factory()))
    results, private = [], []
    cost = 0.0
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        if tenant_id is None:
            raise SystemExit("no tenant: run app.seed.household first")
        subject_ids = dict(s.execute(select(Subject.code, Subject.id)).all())
        prepared = {}
        for case in cases["cases"]:
            ctx = CallContext(request_id=f"eval-tutor-{case['id']}", tenant_id=tenant_id)
            prepared[case["id"]] = tutoring.prepare_explanation(
                s, gateway, ctx, subject_id=subject_ids[case["subject"]], objective_id=None, message=case["message"]
            )
    for case in cases["cases"]:
        prep = prepared[case["id"]]
        citation_critical = bool(subjects.taught_config_for(case["subject"]).retrieval.citation_required_for)
        reply: TutorReply | None = None
        error = None
        dropped = 0
        if prep.plan.answer_allowed:
            try:
                result = gateway.structured(
                    tutoring.TUTOR_ROLE,
                    tutoring.EXPLAIN_PROMPT,
                    prep.variables,
                    TutorReply,
                    CallContext(request_id=f"eval-tutor-{case['id']}", tenant_id=tenant_id),
                )
                # Check what the student is shown: the live tutor keeps only usable citations (engine rule).
                shown = engine.usable_citations(
                    result.value.citations, state=prep.retrieval_state, excerpts=len(prep.chunks)
                )
                dropped = len(result.value.citations) - len(shown)
                reply = result.value.model_copy(update={"citations": shown})
                cost += result.cost_usd or 0.0
            except LLMError as exc:
                error = exc.code
        check = check_reply(
            reply,
            chunks=len(prep.chunks),
            citation_critical=citation_critical,
            answer_allowed=prep.plan.answer_allowed,
            kind=case["kind"],
        )
        results.append(
            {
                "id": case["id"],
                "subject": case["subject"],
                "kind": case["kind"],
                "retrieval_state": prep.retrieval_state,
                "answered": reply is not None,
                "citations": len(reply.citations) if reply else 0,
                "citations_dropped": dropped,
                "uses_general_knowledge": reply.uses_general_knowledge if reply else None,
                "ok": check.ok and error is None,
                "issues": [*check.issues, *([f"llm_error:{error}"] if error else [])],
            }
        )
        private.append({"id": case["id"], "message": case["message"], "reply": reply.message if reply else None})
    passed = sum(r["ok"] for r in results)
    sociology = [r for r in results if r["subject"] == "igcse-sociology" and r["answered"]]
    return {
        "dataset": cases["version"],
        "cases": len(results),
        "pass_rate": passed / len(results),
        "ac_k4_violations": sum(any(i.startswith("uncited") for i in r["issues"]) for r in sociology),
        "ac_k3_violations": sum("answered_without_material" in r["issues"] for r in results),
        "unsafe_outputs": sum("unsafe_output" in r["issues"] for r in results),
        "cost_usd": round(cost, 5),
        "verdict": "pass" if all(r["ok"] for r in results) else "review",
        "results": results,
        "_private": private,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="make the calls (otherwise print the estimate)")
    args = parser.parse_args()
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]
    if not args.run:
        print(
            f"{len(cases)} cases -> {len(cases)} embedding calls + at most {len(cases)} tutor calls (Flash-Lite). "
            f"Estimated cost ~ ${len(cases) * COST_PER_CALL_USD:.3f} (cases without textbook material make no tutor "
            "call). Re-run with --run."
        )
        return
    report = run()
    private = report.pop("_private")
    stamp = f"{datetime.now(UTC):%Y%m%d-%H%M}"
    REPORTS.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"tutor_{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (PRIVATE / f"tutor_{stamp}.json").write_text(json.dumps(private, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
