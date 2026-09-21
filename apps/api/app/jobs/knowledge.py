"""Chunk, embed and search knowledge sources.

Usage (from apps/api):
  uv run python -m app.jobs.knowledge chunk [--source KEY]      # rebuild chunks from stored pages (no LLM)
  uv run python -m app.jobs.knowledge embed [--source KEY]      # embed chunks without embeddings (resumable)
  uv run python -m app.jobs.knowledge search "query" --subject igcse-maths [--objective 5.4]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.db import get_session_factory, session_scope
from app.llm.config import load_roles
from app.llm.factory import build_gateway
from app.llm.gateway import CallContext
from app.modules.curriculum import service as curriculum
from app.modules.curriculum.models import Subject
from app.modules.identity.models import Tenant
from app.modules.knowledge import service
from app.modules.knowledge.manifest import load_all


def _tenant_id():  # noqa: ANN202
    with session_scope(user_id=None, role="system") as s:
        tenant = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        if tenant is None:
            raise SystemExit("no tenant: run app.seed.household first")
        return tenant


def chunk(source: str | None) -> None:
    keys = [source] if source else [src.key for m in load_all() for src in m.sources]
    for key in keys:
        with session_scope(user_id=None, role="system") as s:
            report = service.chunk_source(s, source_key=key)
        if report.skipped_reason:
            print(f"{key:32} skipped: {report.skipped_reason}")
        else:
            print(
                f"{key:32} chunks={report.chunks:5} tagged={report.tagged:5} page_offset={report.page_offset} "
                f"answer_pages_skipped={len(report.skipped_pages)} reused_embeddings={report.reused_embeddings}"
            )


def embed(source: str | None) -> None:
    cfg = load_roles().embeddings
    report = service.embed_pending(
        get_session_factory(),
        build_gateway(),
        tenant_id=_tenant_id(),
        source_key=source,
        batch_size=cfg.batch_size,
        model_name=cfg.model,
    )
    print(f"embedded={report.embedded} remaining={report.remaining}")


def search(query: str, subject_code: str, objective_code: str | None) -> None:
    tenant_id = _tenant_id()
    with session_scope(user_id=None, role="system") as s:
        subject_id = s.scalar(select(Subject.id).where(Subject.code == subject_code))
        if subject_id is None:
            raise SystemExit(f"unknown subject {subject_code}")
        objective_ids = []
        if objective_code:
            found = curriculum.objectives_by_code(s, subject_id).get(objective_code)
            if found is None:
                raise SystemExit(f"unknown objective {objective_code}")
            objective_ids = [found[0]]
        result = service.search(
            s,
            build_gateway(),
            CallContext(request_id="cli_search", tenant_id=tenant_id),
            query=query,
            subject_id=subject_id,
            objective_ids=objective_ids,
        )
    print(f"state={result.state}")
    for c in result.chunks:
        print(
            f"  {c.similarity!s:>6} aligned={c.aligned!s:5} {c.content_kind:15} p.{c.printed_page} "
            f"{(c.heading_path or '')[:70]}"
        )


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.knowledge")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("chunk", "embed"):
        p = sub.add_parser(name)
        p.add_argument("--source")
    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--subject", required=True)
    p_search.add_argument("--objective")
    args = parser.parse_args(argv[1:])
    if args.cmd == "chunk":
        chunk(args.source)
    elif args.cmd == "embed":
        embed(args.source)
    else:
        search(args.query, args.subject, args.objective)


if __name__ == "__main__":
    main(sys.argv)
