"""Local accounts: password credentials and registration requests

Revision ID: a1c7e5d20b43
Revises: f8d3b1a6c2e9
Create Date: 2026-09-20

AUTH_MODE=local (docs/STUDENT-APP.md D7): anyone may register with an email address, but the account is
`pending` until an admin approves it and chooses the streams it may see. Neither table holds student learning
data, so neither is student-scoped; the password hash lives apart from ``app_user``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c7e5d20b43"
down_revision: str | None = "f8d3b1a6c2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_app_user_status"), "app_user", type_="check")
    op.create_check_constraint(
        op.f("ck_app_user_status"), "app_user", "status in ('active','disabled','pending','rejected')"
    )
    op.create_table(
        "user_credential",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("failed_attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_credential_tenant_id", "user_credential", ["tenant_id"])
    op.create_table(
        "registration_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_streams", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("note", sa.String(500), server_default="", nullable=False),
        sa.Column("decision", sa.String(16), server_default="pending", nullable=False),
        sa.Column("granted_streams", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(500), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id"),
        sa.CheckConstraint("decision in ('pending','approved','rejected')", name=op.f("ck_registration_decision")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["app_user.id"]),
    )
    op.create_index("ix_registration_request_tenant_id", "registration_request", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("registration_request")
    op.drop_table("user_credential")
    op.drop_constraint(op.f("ck_app_user_status"), "app_user", type_="check")
    op.create_check_constraint(op.f("ck_app_user_status"), "app_user", "status in ('active','disabled')")
