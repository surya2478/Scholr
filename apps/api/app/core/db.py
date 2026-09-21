"""Database engine, sessions, declarative base and row-level-security request context."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, MetaData, create_engine, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings
from app.core.ids import uuid7

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

EMBEDDING_DIM = 1024


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantScoped:
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.id", ondelete="RESTRICT"), index=True)


class StudentScoped(TenantScoped):
    """Rows that belong to one student. Protected by forced row-level security."""

    student_id: Mapped[UUID] = mapped_column(ForeignKey("student.id", ondelete="CASCADE"), index=True)


# Tables with student_id that must stay readable by the RLS helper function itself.
RLS_EXEMPT_TABLES = frozenset({"guardian_student_link"})


def student_scoped_tables() -> list[str]:
    return sorted(
        t.name for t in Base.metadata.sorted_tables if "student_id" in t.columns and t.name not in RLS_EXEMPT_TABLES
    )


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine, _session_factory
    if url is not None:
        return create_engine(url, pool_pre_ping=True, future=True)
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


Role = Literal["student", "guardian", "admin", "system"]


def set_rls_context(session: Session, *, user_id: UUID | None, role: Role) -> None:
    """Bind the acting user to the current transaction for RLS policies (SET LOCAL semantics)."""
    session.execute(
        text("SELECT set_config('scholr.user_id', :uid, true), set_config('scholr.role', :role, true)"),
        {"uid": str(user_id) if user_id else "", "role": role},
    )


@contextmanager
def session_scope(*, user_id: UUID | None, role: Role) -> Iterator[Session]:
    """A transactional session with RLS context bound. Commits on success."""
    session = get_session_factory()()
    try:
        with session.begin():
            set_rls_context(session, user_id=user_id, role=role)
            yield session
    finally:
        session.close()
