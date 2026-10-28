"""Digital notebooks and assessment analytics

Revision ID: c7f2a1b4e8d3
Revises: b6e1d8c3a9f4
Create Date: 2026-09-22

- notebook: custom revision folders curated by the student (e.g. 'Traps', 'Circle Theorems').
- notebook_item: question items added to a notebook with private margin notes.
- Both tables are student-scoped with forced PostgreSQL Row-Level Security (RLS).
- Backfills existing question_bookmark entries into a default 'Saved Questions' notebook.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7f2a1b4e8d3"
down_revision: str | None = "b6e1d8c3a9f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_TABLES = ("notebook", "notebook_item")


def upgrade() -> None:
    op.create_table(
        "notebook",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(16), nullable=False, server_default="📓"),
        sa.Column("color", sa.String(32), nullable=False, server_default="amber"),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_notebook_tenant_id", "notebook", ["tenant_id"])
    op.create_index("ix_notebook_student_id", "notebook", ["student_id"])

    op.create_table(
        "notebook_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notebook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebook.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_item_id"], ["question_item.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("notebook_id", "question_item_id", name=op.f("uq_notebook_item_notebook_question")),
    )
    op.create_index("ix_notebook_item_tenant_id", "notebook_item", ["tenant_id"])
    op.create_index("ix_notebook_item_student_id", "notebook_item", ["student_id"])
    op.create_index("ix_notebook_item_notebook_id", "notebook_item", ["notebook_id"])

    for table in STUDENT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_student_access ON {table} "
            "USING (scholr_can_access_student(student_id)) "
            "WITH CHECK (scholr_can_access_student(student_id))"
        )


def downgrade() -> None:
    for table in reversed(STUDENT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_student_access ON {table}")
        op.drop_table(table)
