"""Learning sessions and conversations. Conversation text lives only in `message` (never in logs or events)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TimestampMixin


class LearningSession(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "learning_session"
    __table_args__ = (CheckConstraint("mode in ('learn','practice','test')", name="mode"),)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subject.id"))
    objective_id: Mapped[UUID | None] = mapped_column(ForeignKey("learning_objective.id"))
    mode: Mapped[str] = mapped_column(String(16))
    # A command-word drill: a practice session that serves only questions asking for this command word
    # ("evaluate", "to what extent"). Null for an ordinary session (Phase 2, AC-R4).
    command_word: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # learning-engine state (tutoring.engine)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_minutes: Mapped[int] = mapped_column(SmallInteger, default=0)
    memory_summarized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # learning memory job


class Conversation(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "conversation"
    session_id: Mapped[UUID] = mapped_column(ForeignKey("learning_session.id", ondelete="CASCADE"), index=True)


class Message(IdMixin, StudentScoped, Base):
    __tablename__ = "message"
    __table_args__ = (CheckConstraint("role in ('student','tutor','system')", name="role"),)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    assistance_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    retrieval_state: Mapped[str | None] = mapped_column(String(16))
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    safety_status: Mapped[str] = mapped_column(String(32), default="allow")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
