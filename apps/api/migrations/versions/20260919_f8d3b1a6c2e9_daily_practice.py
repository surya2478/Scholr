"""Student app: the daily practice set

Revision ID: f8d3b1a6c2e9
Revises: e7c2a9d4f5b8
Create Date: 2026-09-19

One row per student per day: the questions chosen for today's practice set (docs/STUDENT-APP.md step 4), fixed
once built so the set does not shift while she answers. Student data, so forced row-level security.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8d3b1a6c2e9"
down_revision: str | None = "e7c2a9d4f5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_TABLES = ("daily_practice",)


def upgrade() -> None:
    op.create_table(
        "daily_practice",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("practice_date", sa.Date(), nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "practice_date"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_daily_practice_tenant_id", "daily_practice", ["tenant_id"])
    op.create_index("ix_daily_practice_student_id", "daily_practice", ["student_id"])
    for table in STUDENT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_student_access ON {table} "
            "USING (scholr_can_access_student(student_id)) "
            "WITH CHECK (scholr_can_access_student(student_id))"
        )


def downgrade() -> None:
    for table in STUDENT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_student_access ON {table}")
    op.drop_table("daily_practice")
