"""Persist LLM call telemetry to the llm_call table."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, sessionmaker

from app.core.db import set_rls_context
from app.llm.gateway import LlmCallRecord
from app.llm.models import LlmCall

log = logging.getLogger(__name__)


class DbCallRecorder:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def record(self, rec: LlmCallRecord) -> None:
        # Telemetry must never break the learning flow; failures are logged, not raised.
        try:
            with self._factory() as session, session.begin():
                set_rls_context(session, user_id=None, role="system")
                session.add(
                    LlmCall(
                        tenant_id=rec.tenant_id,
                        student_id=rec.student_id,
                        request_id=rec.request_id,
                        role=rec.role,
                        model=rec.model,
                        provider=rec.provider,
                        prompt_name=rec.prompt_name,
                        prompt_version=rec.prompt_version,
                        input_tokens=rec.input_tokens,
                        output_tokens=rec.output_tokens,
                        cost_usd=rec.cost_usd,
                        latency_ms=rec.latency_ms,
                        status=rec.status,
                        fallback_used=rec.fallback_used,
                        error_code=rec.error_code,
                    )
                )
        except Exception:  # noqa: BLE001
            log.exception("failed to record llm_call (request_id=%s)", rec.request_id)
