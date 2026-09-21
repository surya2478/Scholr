from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class Enrollment(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "enrollment"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id"),
        CheckConstraint("status in ('active','paused','completed')", name="status"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    tier: Mapped[str | None] = mapped_column(String(16))
    exam_session: Mapped[str | None] = mapped_column(String(7))  # "2027-06"
    status: Mapped[str] = mapped_column(String(16), default="active")


class TeachingPlanEntry(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "teaching_plan_entry"
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    term: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(300))
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    topic_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    source: Mapped[str] = mapped_column(String(200))


class Commitment(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "commitment"
    __table_args__ = (CheckConstraint("kind in ('iit_class','extracurricular','school','other')", name="kind"),)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    rrule: Mapped[str] = mapped_column(String(300))  # RFC 5545 recurrence rule
    start_time: Mapped[str | None] = mapped_column(String(5))  # "17:00" local time
    duration_min: Mapped[int] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)


class Availability(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "availability"
    __table_args__ = (
        UniqueConstraint("student_id", "weekday"),
        CheckConstraint("weekday between 0 and 6", name="weekday"),
        CheckConstraint("minutes between 0 and 720", name="minutes"),
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = Monday
    minutes: Mapped[int] = mapped_column(SmallInteger)


class UpcomingAssessment(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "upcoming_assessment"
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    title: Mapped[str] = mapped_column(String(200))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    notes: Mapped[str | None] = mapped_column(Text)


class SchoolResult(IdMixin, TimestampMixin, StudentScoped, Base):
    """Independent evidence: marks from school tests."""

    __tablename__ = "school_result"
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    title: Mapped[str] = mapped_column(String(200))
    assessed_on: Mapped[date] = mapped_column(Date)
    score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    max_score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
