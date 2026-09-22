"""Run a job's model calls through OpenRouter's Batch API (docs/STUDENT-APP.md §17).

The user's rule (21 Sep 2026) puts batch jobs on `:batch` model variants, which exist only behind the Batch API:
requests are submitted together and come back within 24 hours. This module submits one batch per job round,
saves a small state file so an interrupted wait can be picked up again (`--resume <batch_id>`), polls until the
batch ends, and submits the requests whose reply was unreadable once more. It never falls back to a live model.

The state file holds the batch id, role, model, prompt and the request ids — no lesson or student text.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.config import API_ROOT
from app.llm.gateway import BatchHandle, BatchItem, BatchOutcome, CallContext, LLMGateway, LLMResult
from app.llm.transport import TransportError

STATE = API_ROOT.parents[1] / "evals" / "runs" / "batches"
POLL_SECONDS = 30
REGISTER_GRACE_SECONDS = 600
ROUNDS = 2  # a reply that fails its schema is queued once more; a batch cannot repair in place


def _save(handle: BatchHandle, tag: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"{handle.id}.json").write_text(json.dumps({"tag": tag, **asdict(handle)}, indent=2), encoding="utf-8")


def load(batch_id: str) -> BatchHandle:
    data = json.loads((STATE / f"{batch_id}.json").read_text(encoding="utf-8"))
    data.pop("tag", None)
    data["custom_ids"] = tuple(data["custom_ids"])
    return BatchHandle(**data)


def wait[T: BaseModel](
    gateway: LLMGateway,
    handle: BatchHandle,
    schema: type[T],
    ctx: CallContext,
    *,
    poll_seconds: float = POLL_SECONDS,
    say: Callable[[str], None] = print,
) -> BatchOutcome[T]:
    started = time.monotonic()
    while True:
        try:
            outcome = gateway.batch_collect(handle, schema, ctx)
        except TransportError as exc:
            # A batch just submitted can answer "not found" for a short while before OpenRouter lists it.
            if exc.code == "http_404" and time.monotonic() - started < REGISTER_GRACE_SECONDS:
                say(f"  batch {handle.id}: not listed yet")
                time.sleep(poll_seconds)
                continue
            raise
        if outcome is not None:
            return outcome
        status = gateway.batch_status(handle)
        counts = status.get("request_counts") or {}
        minutes = (time.monotonic() - started) / 60
        say(
            f"  batch {handle.id}: {status.get('status')}, {counts.get('completed', 0)}/{counts.get('total', '?')} done"
            f" ({minutes:.0f} min)"
        )
        time.sleep(poll_seconds)


def run[T: BaseModel](
    gateway: LLMGateway,
    role: str,
    prompt_name: str,
    items: Sequence[BatchItem],
    schema: type[T],
    tenant_id: UUID,
    *,
    tag: str,
    prompt_version: str | None = None,
    resume: str | None = None,
    say: Callable[[str], None] = print,
) -> tuple[dict[str, LLMResult[T]], dict[str, str], float]:
    """(results by custom_id, failures by custom_id, cost). Up to ROUNDS batches; later rounds only for replies
    that failed their schema."""
    ctx = CallContext(request_id=f"batch:{tag}:{datetime.now(UTC):%Y%m%d%H%M%S}", tenant_id=tenant_id)
    results: dict[str, LLMResult[T]] = {}
    failures: dict[str, str] = {}
    cost = 0.0
    pending = list(items)
    for round_ in range(ROUNDS):
        if resume and round_ == 0:
            handle = load(resume)
            pending = [i for i in pending if i.custom_id in handle.custom_ids]
        elif not pending:
            break
        else:
            handle = gateway.batch_submit(role, prompt_name, pending, schema, ctx, prompt_version=prompt_version)
            _save(handle, tag)
        say(f"  submitted batch {handle.id} ({len(handle.custom_ids)} requests, {handle.model})")
        outcome = wait(gateway, handle, schema, ctx, say=say)
        cost += outcome.cost_usd
        results.update(outcome.results)
        retry = {cid for cid, code in outcome.failures.items() if code == "invalid_output"}
        failures = {cid: code for cid, code in {**failures, **outcome.failures}.items() if cid not in results}
        pending = [i for i in pending if i.custom_id in retry]
    return results, failures, round(cost, 6)
