from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, StudentScoped, TenantScoped, TimestampMixin

GUARDIAN_SCOPES = ("progress", "mastery", "assessments", "plans", "conversations", "safety", "memory")


class Tenant(IdMixin, TimestampMixin, Base):
    __tablename__ = "tenant"
    name: Mapped[str] = mapped_column(String(200))


class AppUser(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role in ('student','guardian','admin')", name="role"),
        CheckConstraint("status in ('active','disabled')", name="status"),
    )
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")


class Student(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "student"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    year_group: Mapped[str] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dubai", server_default="Asia/Dubai")
    locale: Mapped[str] = mapped_column(String(16), default="en", server_default="en")


class Guardian(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "guardian"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), unique=True)


class GuardianStudentLink(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "guardian_student_link"
    __table_args__ = (UniqueConstraint("guardian_id", "student_id"),)
    guardian_id: Mapped[UUID] = mapped_column(ForeignKey("guardian.id", ondelete="CASCADE"), index=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    granted_by: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentRecord(IdMixin, TimestampMixin, StudentScoped, Base):
    __tablename__ = "consent_record"
    __table_args__ = (CheckConstraint("kind in ('guardian_consent','student_assent')", name="kind"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))
    kind: Mapped[str] = mapped_column(String(32))
    policy_version: Mapped[str] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserCredential(IdMixin, TimestampMixin, TenantScoped, Base):
    """An account's password hash and its lockout state (AUTH_MODE=local, docs/STUDENT-APP.md D7).

    Separate from ``app_user`` so nothing that reads a user reads a hash by accident.
    """

    __tablename__ = "user_credential"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    failed_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_sign_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegistrationRequest(IdMixin, TimestampMixin, TenantScoped, Base):
    """What a new account asked for, and what the admin decided (D7).

    The streams are requested here and granted on approval; the account can do nothing while it is pending.
    """

    __tablename__ = "registration_request"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint("decision in ('pending','approved','rejected')", name="decision"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    requested_streams: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    decision: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    granted_streams: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), default="", server_default="")
