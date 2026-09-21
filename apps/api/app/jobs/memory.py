"""Summarize ended study sessions into learning memory (role `summarizer`, Flash-Lite).

Usage (from apps/api):
  uv run python -m app.jobs.memory pending                 # how many sessions are waiting (no LLM)
  uv run python -m app.jobs.memory summarize [--limit 20]  # summarize them; sessions with little activity make no call
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from functools import partial

import app.models_registry  # noqa: F401
from app.core.db import get_session_factory, session_scope
from app.llm.factory import build_gateway
from app.llm.recorder import DbCallRecorder
from app.modules.memory import service
from app.modules.tutoring import service as tutoring

COST_PER_CALL_USD = 0.0004  # measured order of magnitude for Flash-Lite at ~1.5k input / 300 output tokens


def pending(limit: int) -> None:
    with session_scope(user_id=None, role="system") as s:
        ids = tutoring.sessions_to_summarize(s, limit=limit)
    print(f"sessions waiting: {len(ids)} (at most ~${len(ids) * COST_PER_CALL_USD:.4f} if every one needs a call)")


def summarize(limit: int) -> None:
    with session_scope(user_id=None, role="system") as s:
        ids = tutoring.sessions_to_summarize(s, limit=limit)
    gateway = build_gateway(DbCallRecorder(get_session_factory()))
    opener = partial(session_scope, user_id=None, role="system")
    total = 0.0
    for session_id in ids:
        report = service.summarize_session(
            opener, gateway, session_id, request_id=f"job-memory-{session_id}", now=datetime.now(UTC)
        )
        total += report.cost_usd
        print(
            f"{session_id} {report.status:16} created={report.created} merged={report.merged} "
            f"superseded={report.superseded} rejected={list(report.rejected)}"
        )
    print(f"done: {len(ids)} sessions, cost ${total:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pending", "summarize"):
        p = sub.add_parser(name)
        p.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    (pending if args.command == "pending" else summarize)(args.limit)


if __name__ == "__main__":
    main()
