from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class StudyAssignment(IdMixin, TimestampMixin, StudentScoped, Base):
    """Validation study arm assignment for a matched topic pair (PHASE-1 §5)."""

    __tablename__ = "study_assignment"
    __table_args__ = (CheckConstraint("arm in ('app','control')", name="arm"),)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    pair_code: Mapped[str] = mapped_column(String(32))
    arm: Mapped[str] = mapped_column(String(8))
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    assignment_method: Mapped[str] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    crossover_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
