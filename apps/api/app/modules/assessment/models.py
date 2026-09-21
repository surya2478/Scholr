from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TenantScoped, TimestampMixin

ASSESSMENT_KINDS = ("practice", "quiz", "baseline", "post", "retention", "exam_style")


class QuestionItem(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "question_item"
    __table_args__ = (
        CheckConstraint("origin in ('past_paper','textbook','school','template','generated')", name="origin"),
        CheckConstraint("verification_status in ('unverified','verified','rejected')", name="verification"),
        # AC-E1: generated items can only be served once verified; enforced at selection and here.
        CheckConstraint("not (origin = 'generated' and reserved_for_study)", name="generated_not_reserved"),
        # AC-E1: a template/generated item can be verified only when SymPy verified its answer (templates.generate).
        CheckConstraint(
            "origin not in ('template','generated') OR verification_status <> 'verified' "
            "OR coalesce((answer_spec ->> 'sympy_verified')::boolean, false)",
            name="generated_needs_sympy_verification",
        ),
        UniqueConstraint("source_ref"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"), index=True)
    origin: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("source.id"))
    source_ref: Mapped[str | None] = mapped_column(String(64))  # e.g. "0580/21/MJ24/Q7a"
    parent_ref: Mapped[str | None] = mapped_column(String(64))  # e.g. "0580/21/MJ24/Q7"
    stem: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)  # shared question/source text
    marks: Mapped[int] = mapped_column(SmallInteger)
    command_word: Mapped[str | None] = mapped_column(String(32))
    objective_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    skill_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    topic_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PGUUID(as_uuid=True)), default=list)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    calculator_allowed: Mapped[bool | None]
    has_diagram: Mapped[bool] = mapped_column(default=False)
    answer_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    mark_scheme: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")
    verified_by: Mapped[str | None] = mapped_column(String(100))
    reserved_for_study: Mapped[bool] = mapped_column(default=False)
    generator_version: Mapped[str | None] = mapped_column(String(32))
    source_pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, server_default="{}")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class Assessment(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "assessment"
    __table_args__ = (
        CheckConstraint("kind in ('practice','quiz','baseline','post','retention','exam_style')", name="kind"),
        CheckConstraint("status in ('draft','in_progress','submitted','evaluated','abandoned')", name="status"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    kind: Mapped[str] = mapped_column(String(16))
    form_code: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    selection_rule_version: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentItem(Base):
    __tablename__ = "assessment_item"
    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("assessment.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    question_item_id: Mapped[UUID] = mapped_column(ForeignKey("question_item.id"))


class Attempt(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "attempt"
    __table_args__ = (
        UniqueConstraint("student_id", "idempotency_key"),
        CheckConstraint("pre_confidence between 1 and 4", name="pre_confidence"),
        CheckConstraint("max_assistance_level between 0 and 5", name="assistance"),
    )
    question_item_id: Mapped[UUID] = mapped_column(ForeignKey("question_item.id"), index=True)
    assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment.id", ondelete="SET NULL"))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_session.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    answer_text: Mapped[str | None] = mapped_column(Text)  # typed working
    final_answer: Mapped[str | None] = mapped_column(Text)
    answer_image_uris: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    transcription: Mapped[str | None] = mapped_column(Text)  # working read from photos
    transcription_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    transcription_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pre_confidence: Mapped[int | None] = mapped_column(SmallInteger)
    max_assistance_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    time_spent_s: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExaminerInsight(IdMixin, TimestampMixin, TenantScoped, Base):
    """One short point, in our own words, from a Principal Examiner Report about one question (AC-R6).

    Which question it belongs to comes from the report's own layout (``examiner_reports.segment_report``), not
    from the model. ``question_ref`` is null for points about the whole paper. The report's wording is never
    stored — only ``text``, which ``examiner_reports.guard`` has checked shares no long run of words with it.
    """

    __tablename__ = "examiner_insight"
    __table_args__ = (CheckConstraint("kind in ('common_error','what_scored','advice')", name="kind"),)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"), index=True)
    syllabus_code: Mapped[str] = mapped_column(String(8))
    component: Mapped[str] = mapped_column(String(4))
    exam_series: Mapped[str] = mapped_column(String(8))  # "MJ25"
    report_title: Mapped[str] = mapped_column(String(300))  # the source's own title, for attribution
    question_ref: Mapped[str | None] = mapped_column(String(32))  # "1(a)(ii)"; null = whole paper
    item_ref: Mapped[str | None] = mapped_column(String(64), index=True)  # question_item.source_ref it attaches to
    kind: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(SmallInteger)
    pages: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    segment_key: Mapped[str] = mapped_column(String(48))  # "11:1(a)(ii)" or "11:paper"
    segment_sha: Mapped[str] = mapped_column(String(64))
    segmenter_version: Mapped[str] = mapped_column(String(16))
    prompt_version: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
