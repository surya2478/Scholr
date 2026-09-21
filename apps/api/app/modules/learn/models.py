from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TenantScoped, TimestampMixin


class Lesson(IdMixin, TimestampMixin, TenantScoped, Base):
    """Scholr's explanation of one objective, written from the student's course material (docs/STUDENT-APP.md).

    Course content, not student data: one row per objective, shared, no `student_id` (like `question_item`).
    `status` is `ready`, or `not_enough_material` when retrieval did not reach the grounding floor — stored so
    the page can say so without calling the model again until the corpus changes.
    """

    __tablename__ = "lesson"
    __table_args__ = (
        UniqueConstraint("objective_id"),
        CheckConstraint("status in ('ready','not_enough_material')", name="status"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"), index=True)
    objective_id: Mapped[UUID] = mapped_column(ForeignKey("learning_objective.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24))
    retrieval_state: Mapped[str] = mapped_column(String(8))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_chunk_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    corpus_key: Mapped[str] = mapped_column(String(64))  # hash of the excerpts it was written from
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    guard_version: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
