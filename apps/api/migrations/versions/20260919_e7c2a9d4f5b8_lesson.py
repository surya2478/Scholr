"""Student app: topic lessons

Revision ID: e7c2a9d4f5b8
Revises: d4a8e2f6b1c7
Create Date: 2026-09-19

One stored explanation per learning objective (docs/STUDENT-APP.md, AC-U3–U6). Course content shared by every
viewer, like `question_item`: `tenant_id`, no `student_id`, so no row-level-security policy. Reading one is a
student event (`explanation_viewed`), recorded in `learning_event`, not here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7c2a9d4f5b8"
down_revision: str | None = "d4a8e2f6b1c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("objective_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("retrieval_state", sa.String(8), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("source_chunk_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("corpus_key", sa.String(64), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("guard_version", sa.String(32), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('ready','not_enough_material')", name="status"),
        sa.UniqueConstraint("objective_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"]),
        sa.ForeignKeyConstraint(["objective_id"], ["learning_objective.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_lesson_tenant_id", "lesson", ["tenant_id"])
    op.create_index("ix_lesson_subject_id", "lesson", ["subject_id"])


def downgrade() -> None:
    op.drop_table("lesson")
