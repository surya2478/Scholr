from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class Goal(IdMixin, TimestampMixin, StudentScoped, Base):
    """A goal Scholr tracks. Progress is always derived from evidence, never self-reported (AC-G1)."""

    __tablename__ = "goal"
    __table_args__ = (
        CheckConstraint("status in ('proposed','active','achieved','dropped')", name="status"),
        CheckConstraint(
            "measure in ('topics_secure','active_days_per_week','answers_without_help','open_mistakes')",
            name="measure",
        ),
    )
    kind: Mapped[str] = mapped_column(String(32))
    statement: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    # What is counted, what it has to reach, and where it stood when the goal was set. The baseline is what
    # makes a progress bar honest: without it, "6 of 8 topics" looks like progress even if it started at 6.
    measure: Mapped[str] = mapped_column(String(32))
    target_value: Mapped[float] = mapped_column(Float)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("subject.id"))
    # "Set with the student": a goal a parent proposes waits for her to agree before it is active.
    proposed_by_role: Mapped[str] = mapped_column(String(16))
    agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rule_version: Mapped[str] = mapped_column(String(32))


class StudyPlan(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "study_plan"
    __table_args__ = (UniqueConstraint("student_id", "plan_date", "generator_version"),)
    plan_date: Mapped[date] = mapped_column(Date)
    generator_version: Mapped[str] = mapped_column(String(32))
    capacity_minutes: Mapped[int] = mapped_column(SmallInteger)
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class PlanItem(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "plan_item"
    __table_args__ = (
        CheckConstraint(
            "kind in ('school_topic','revision','mistake_fix','practice','challenge','assessment','reinforcement')",
            name="kind",
        ),
        CheckConstraint("status in ('planned','in_progress','completed','skipped')", name="status"),
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("study_plan.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    objective_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_objective.id"))
    kind: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(SmallInteger)
    est_minutes: Mapped[int] = mapped_column(SmallInteger)
    priority: Mapped[float] = mapped_column(Float)
    reason_code: Mapped[str] = mapped_column(String(48))
    # A sentence written when the plan was built, when the template reason cannot say enough on its own
    # (a reinforcement item names the external class it came from).
    reason_detail: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="planned")


class DailyPractice(IdMixin, TimestampMixin, StudentScoped, Base):
    """Today's practice set, fixed once built so it does not shift while she answers (docs/STUDENT-APP.md step 4).

    `items` is the chosen questions in order: [{item_id, objective_id, reason_code}]. Progress is not stored here;
    it is read from her attempts and their evaluations.
    """

    __tablename__ = "daily_practice"
    __table_args__ = (UniqueConstraint("student_id", "practice_date"),)
    practice_date: Mapped[date] = mapped_column(Date)
    rule_version: Mapped[str] = mapped_column(String(32))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
