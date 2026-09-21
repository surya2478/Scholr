"""Retrieval eval (AC-K2): recall@8 of the expected objective and retrieval-state agreement.

Usage (from apps/api):
  uv run python -m app.jobs.retrieval_eval            # estimate only (no calls)
  uv run python -m app.jobs.retrieval_eval --run      # run: one embedding call per query (bge-m3), no chat model

The report (metrics and case ids only, no textbook text) goes to evals/reports/.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import API_ROOT
from app.core.db import get_session_factory, session_scope
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext
from app.llm.recorder import DbCallRecorder
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.identity.models import Tenant
from app.modules.knowledge import service as knowledge
from app.modules.knowledge.models import KnowledgeChunk

REPO = API_ROOT.parents[1]
DATASET = REPO / "evals" / "datasets" / "retrieval" / "cases.yaml"
REPORTS = REPO / "evals" / "reports"
K = 8
TARGET_RECALL = 0.85  # AC-K2
TARGET_STATE = 0.80
EMBED_COST_PER_QUERY_USD = 0.000001  # ~20 tokens at bge-m3 pricing


def state_matches(expected: str, actual: str) -> bool:
    """HIGH and MEDIUM both count as grounded; LOW and NONE both count as not grounded enough to rely on."""
    grounded = {"HIGH", "MEDIUM"}
    return (expected in grounded) == (actual in grounded) if expected != actual else True


def run() -> dict[str, Any]:
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))
    gateway = build_gateway(DbCallRecorder(get_session_factory()))
    results = []
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        if tenant_id is None:
            raise SystemExit("no tenant: run app.seed.household first")
        subject_ids = dict(s.execute(select(Subject.code, Subject.id)).all())
        for case in cases["cases"]:
            subject_id = subject_ids[case["subject"]]
            ctx = CallContext(request_id=f"eval-retrieval-{case['id']}", tenant_id=tenant_id)
            result = knowledge.search(s, gateway, ctx, query=case["query"], subject_id=subject_id, k=K)
            chunk_objectives = dict(
                s.execute(
                    select(KnowledgeChunk.id, KnowledgeChunk.objective_ids).where(
                        KnowledgeChunk.id.in_([c.id for c in result.chunks])
                    )
                ).all()
            )
            expected_code = case.get("expected_objective")
            hit = None
            if expected_code:
                by_code = curriculum.objectives_by_code(s, subject_id)
                expected_ids: set[UUID] = {by_code[expected_code][0]} if expected_code in by_code else set()
                hit = any(set(chunk_objectives.get(c.id) or []) & expected_ids for c in result.chunks[:K])
            results.append(
                {
                    "id": case["id"],
                    "subject": case["subject"],
                    "expected_state": case["expected_state"],
                    "state": result.state,
                    "state_exact": result.state == case["expected_state"],
                    "state_ok": state_matches(case["expected_state"], result.state),
                    "recall_hit": hit,
                    "top_similarity": max((c.similarity or 0 for c in result.chunks), default=None),
                }
            )
    with_expected = [r for r in results if r["recall_hit"] is not None]
    recall = sum(r["recall_hit"] for r in with_expected) / len(with_expected) if with_expected else None
    state_rate = sum(r["state_ok"] for r in results) / len(results)
    return {
        "dataset": cases["version"],
        "k": K,
        "cases": len(results),
        "recall_at_k": recall,
        "state_agreement": state_rate,
        "state_exact": sum(r["state_exact"] for r in results) / len(results),
        "targets": {"recall_at_k": TARGET_RECALL, "state_agreement": TARGET_STATE},
        "verdict": "pass" if recall is not None and recall >= TARGET_RECALL and state_rate >= TARGET_STATE else "fail",
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="make the calls (otherwise print the estimate)")
    args = parser.parse_args()
    cases = yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]
    if not args.run:
        print(
            f"{len(cases)} queries -> {len(cases)} embedding calls, no chat model. "
            f"Estimated cost ~ ${len(cases) * EMBED_COST_PER_QUERY_USD:.5f}. Re-run with --run."
        )
        return
    report = run()
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"retrieval_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    print(f"report: {Path(path).relative_to(REPO)}")


if __name__ == "__main__":
    main()
