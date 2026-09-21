"""ARQ background worker for PDF ingestion and OCR jobs.

Usage (from apps/api):
  python -m arq app.jobs.worker.WorkerSettings
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from arq.connections import ArqRedis, RedisSettings, create_pool
from sqlalchemy import select

import app.models_registry  # noqa: F401
from app.core.config import get_settings
from app.core.db import get_session_factory, session_scope
from app.llm.factory import build_gateway
from app.modules.identity.models import Tenant
from app.modules.knowledge.extraction import (
    RegisteredDocument,
    extract_text_layer,
    register_manifest,
    run_ocr,
)
from app.modules.knowledge.manifest import load_all
from app.modules.knowledge.ocr import OcrOptions

log = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_url)


def _get_tenant_id() -> UUID:
    with session_scope(user_id=None, role="system") as s:
        tenant_id = s.scalar(select(Tenant.id).order_by(Tenant.created_at))
        if tenant_id is None:
            raise RuntimeError("No tenant found: seed household first")
        return tenant_id


async def ingest_manifest_task(ctx: dict[str, Any], manifest_subject: str | None = None) -> dict[str, Any]:
    """Ingest documents from manifest(s) and extract text layers.

    Runs in a background thread executor so blocking PDF I/O doesn't block the event loop.
    """
    settings = get_settings()
    subjects_dir = settings.resolve_path(settings.subjects_dir)
    tenant_id = _get_tenant_id()

    def _sync_ingest() -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        manifests = load_all()
        if manifest_subject:
            manifests = [m for m in manifests if m.subject == manifest_subject]

        for manifest in manifests:
            with session_scope(user_id=None, role="system") as s:
                registered = register_manifest(s, tenant_id=tenant_id, manifest=manifest, subjects_dir=subjects_dir)
                for doc in registered:
                    written = extract_text_layer(s, tenant_id=tenant_id, doc=doc) if doc.has_text_layer else 0
                    results.append(
                        {
                            "source_key": doc.source_key,
                            "created": doc.created,
                            "page_count": doc.page_count,
                            "has_text_layer": doc.has_text_layer,
                            "pages_extracted": written,
                        }
                    )
        return {"manifest_subject": manifest_subject, "documents": results}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_ingest)


async def ocr_source_task(
    ctx: dict[str, Any],
    source_key: str,
    pages: list[int] | None = None,
    concurrency: int = 4,
) -> dict[str, Any]:
    """Execute vision OCR on unparsed pages of a registered source document."""
    settings = get_settings()
    subjects_dir = settings.resolve_path(settings.subjects_dir)
    tenant_id = _get_tenant_id()

    def _sync_ocr() -> dict[str, Any]:
        docs: dict[str, RegisteredDocument] = {}
        for manifest in load_all():
            with session_scope(user_id=None, role="system") as s:
                for doc in register_manifest(s, tenant_id=tenant_id, manifest=manifest, subjects_dir=subjects_dir):
                    docs[doc.source_key] = doc

        if source_key not in docs:
            raise ValueError(f"Unknown source key: {source_key}")

        doc = docs[source_key]
        if doc.has_text_layer:
            return {
                "source_key": source_key,
                "status": "skipped",
                "reason": "source has text layer; OCR not needed",
            }

        src = next(src for manifest in load_all() for src in manifest.sources if src.key == source_key)
        options = OcrOptions(
            role=src.ocr_role,
            prompt=src.ocr_prompt,
            output=src.ocr_output,
            dpi=src.ocr_dpi,
            bands=src.ocr_bands,
        )

        gateway = ctx.get("gateway") or build_gateway()
        report = run_ocr(
            get_session_factory(),
            gateway,
            tenant_id=tenant_id,
            doc=doc,
            pages=pages,
            concurrency=concurrency,
            options=options,
            postprocess=src.ocr_postprocess,
        )

        return {
            "source_key": source_key,
            "requested": report.requested,
            "written": report.written,
            "failed": report.failed,
            "cost_usd": report.cost_usd,
            "stopped_reason": report.stopped_reason,
        }

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_ocr)


async def ocr_page_task(ctx: dict[str, Any], source_key: str, page_number: int) -> dict[str, Any]:
    """Execute vision OCR on a single page of a registered source."""
    return await ocr_source_task(ctx, source_key=source_key, pages=[page_number], concurrency=1)


async def startup(ctx: dict[str, Any]) -> None:
    log.info("ARQ worker starting up...")
    ctx["gateway"] = build_gateway()
    log.info("ARQ worker initialized successfully.")


async def shutdown(ctx: dict[str, Any]) -> None:
    log.info("ARQ worker shutting down...")


class WorkerSettings:
    """Settings class used by the `arq` CLI to run the worker."""

    functions = [ingest_manifest_task, ocr_source_task, ocr_page_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 3600


async def get_arq_redis_pool() -> ArqRedis:
    """Create and return an ArqRedis client pool."""
    return await create_pool(get_redis_settings())


async def enqueue_ingest_manifest(
    manifest_subject: str | None = None,
) -> str | None:
    """Enqueue an ingest manifest job into ARQ."""
    try:
        pool = await get_arq_redis_pool()
        job = await pool.enqueue_job("ingest_manifest_task", manifest_subject=manifest_subject)
        await pool.aclose()
        return job.job_id if job else None
    except Exception as exc:
        log.warning("Could not enqueue ingest_manifest_task to Redis: %s", exc)
        return None


async def enqueue_ocr_source(
    source_key: str,
    pages: list[int] | None = None,
    concurrency: int = 4,
) -> str | None:
    """Enqueue an OCR source job into ARQ."""
    try:
        pool = await get_arq_redis_pool()
        job = await pool.enqueue_job(
            "ocr_source_task",
            source_key=source_key,
            pages=pages,
            concurrency=concurrency,
        )
        await pool.aclose()
        return job.job_id if job else None
    except Exception as exc:
        log.warning("Could not enqueue ocr_source_task to Redis: %s", exc)
        return None
