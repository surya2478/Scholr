from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, Float, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

VERIFICATION_CHECK = "verification_status in ('unverified','verified')"


class Curriculum(IdMixin, TimestampMixin, Base):
    __tablename__ = "curriculum"
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class LearningPath(IdMixin, TimestampMixin, Base):
    __tablename__ = "path"
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Syllabus(IdMixin, TimestampMixin, Base):
    __tablename__ = "syllabus"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "code", "version"),
        CheckConstraint(VERIFICATION_CHECK, name="verification"),
    )
    curriculum_id: Mapped[UUID] = mapped_column(ForeignKey("curriculum.id"))
    code: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(32))
    first_exam_year: Mapped[int | None] = mapped_column(SmallInteger)
    last_exam_year: Mapped[int | None] = mapped_column(SmallInteger)
    tiers: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")
    source_note: Mapped[str | None] = mapped_column(Text)


class ExamComponent(IdMixin, TimestampMixin, Base):
    __tablename__ = "exam_component"
    __table_args__ = (
        UniqueConstraint("syllabus_id", "code"),
        CheckConstraint(VERIFICATION_CHECK, name="verification"),
    )
    syllabus_id: Mapped[UUID] = mapped_column(ForeignKey("syllabus.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    tier: Mapped[str | None] = mapped_column(String(16))
    duration_min: Mapped[int | None] = mapped_column(SmallInteger)
    marks: Mapped[int | None] = mapped_column(SmallInteger)
    calculator_allowed: Mapped[bool | None]
    structure_note: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")


class Subject(IdMixin, TimestampMixin, Base):
    __tablename__ = "subject"
    path_id: Mapped[UUID] = mapped_column(ForeignKey("path.id"))
    syllabus_id: Mapped[UUID | None] = mapped_column(ForeignKey("syllabus.id"))
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    config_key: Mapped[str] = mapped_column(String(64))


class Topic(IdMixin, TimestampMixin, Base):
    """Topic tree: depth 0 = topic, depth 1 = subtopic."""

    __tablename__ = "topic"
    __table_args__ = (
        UniqueConstraint("subject_id", "code"),
        CheckConstraint(VERIFICATION_CHECK, name="verification"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    depth: Mapped[int] = mapped_column(SmallInteger, default=0)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(SmallInteger, default=0)
    syllabus_ref: Mapped[str | None] = mapped_column(String(64))
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")


class LearningObjective(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_objective"
    __table_args__ = (
        UniqueConstraint("topic_id", "code"),
        CheckConstraint("tier in ('core','extended','all')", name="tier"),
        CheckConstraint(VERIFICATION_CHECK, name="verification"),
    )
    topic_id: Mapped[UUID] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    statement: Mapped[str] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(String(16), default="all")
    syllabus_ref: Mapped[str | None] = mapped_column(String(64))
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")


class Skill(IdMixin, TimestampMixin, Base):
    __tablename__ = "skill"
    __table_args__ = (
        UniqueConstraint("subject_id", "code"),
        CheckConstraint("kind in ('assessment_objective','process')", name="kind"),
    )
    subject_id: Mapped[UUID | None] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32))


class Concept(IdMixin, TimestampMixin, Base):
    """Curriculum-neutral idea. Objectives from different curricula meet here (ARCHITECTURE §3)."""

    __tablename__ = "concept"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Why the mapping is what it is, when it needs saying — e.g. the external course goes beyond IGCSE and
    # only the ground underneath it is mapped. Shown to the student with a reinforcement suggestion.
    note: Mapped[str | None] = mapped_column(Text)


class ObjectiveConcept(Base):
    __tablename__ = "objective_concept"
    objective_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_objective.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[UUID] = mapped_column(ForeignKey("concept.id", ondelete="CASCADE"), primary_key=True)


class ConceptPrerequisite(Base):
    __tablename__ = "concept_prerequisite"
    concept_id: Mapped[UUID] = mapped_column(ForeignKey("concept.id", ondelete="CASCADE"), primary_key=True)
    prerequisite_id: Mapped[UUID] = mapped_column(ForeignKey("concept.id", ondelete="CASCADE"), primary_key=True)
    strength: Mapped[float] = mapped_column(Float, default=1.0)
