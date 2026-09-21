"""Unit tests for ARQ background worker and task definitions."""

from __future__ import annotations

import pytest

from app.jobs.worker import (
    WorkerSettings,
    get_redis_settings,
    ingest_manifest_task,
    ocr_page_task,
    ocr_source_task,
)


def test_worker_settings_configuration() -> None:
    assert ingest_manifest_task in WorkerSettings.functions
    assert ocr_source_task in WorkerSettings.functions
    assert ocr_page_task in WorkerSettings.functions
    assert WorkerSettings.max_jobs == 10
    assert WorkerSettings.job_timeout == 3600

    redis_settings = get_redis_settings()
    assert redis_settings.host is not None
    assert redis_settings.port is not None


@pytest.mark.anyio
async def test_enqueue_task_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.jobs import worker

    class DummyJob:
        job_id = "job-12345"

    class DummyPool:
        async def enqueue_job(self, *args, **kwargs):
            return DummyJob()

        async def aclose(self):
            pass

    async def dummy_pool():
        return DummyPool()

    monkeypatch.setattr(worker, "get_arq_redis_pool", dummy_pool)

    job_id = await worker.enqueue_ingest_manifest(manifest_subject="igcse-maths")
    assert job_id == "job-12345"

    job_id = await worker.enqueue_ocr_source(source_key="collins-igcse-maths-4e", pages=[1, 2])
    assert job_id == "job-12345"
