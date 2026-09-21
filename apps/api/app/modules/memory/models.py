from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class LearningMemory(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "learning_memory"
    __table_args__ = (
        CheckConstraint("kind in ('strength','difficulty','misconception','preference','note')", name="kind"),
        CheckConstraint("status in ('active','superseded')", name="status"),
        CheckConstraint("cardinality(evidence_event_ids) >= 1", name="has_evidence"),  # AC-M3
    )
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("subject.id"))
    kind: Mapped[str] = mapped_column(String(16))
    statement: Mapped[str] = mapped_column(Text)
    evidence_event_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    status: Mapped[str] = mapped_column(String(16), default="active")
    superseded_by: Mapped[UUID | None] = mapped_column(ForeignKey("learning_memory.id"))
