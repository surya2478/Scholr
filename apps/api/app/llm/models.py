from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantScoped


class LlmCall(IdMixin, TenantScoped, Base):
    """Telemetry for every LLM call (AC-O1). No prompt or response text is stored here."""

    __tablename__ = "llm_call"
    student_id: Mapped[UUID | None] = mapped_column(ForeignKey("student.id", ondelete="SET NULL"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(64))
    prompt_name: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # ok | error
    fallback_used: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(String(48))
    # Client-side default: inserts must not need RETURNING (llm_call is write-only for non-admin roles).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
