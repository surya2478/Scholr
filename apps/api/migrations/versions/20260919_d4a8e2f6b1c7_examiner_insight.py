"""Phase 2: examiner-report insights per question

Revision ID: d4a8e2f6b1c7
Revises: c5e1d8a2f403
Create Date: 2026-09-19

Short points, in Scholr's own words, from the Principal Examiner Reports, each tied to the question it is
about (AC-R6). The question comes from the report's layout, found in code; the model only paraphrases.

Like `question_item`, this is course content rather than student data: it carries `tenant_id` but no
`student_id`, so it needs no row-level-security policy. Who may *see* a point — only after an answer to that
question has been marked — is decided in the evaluation service.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a8e2f6b1c7"
down_revision: str | None = "c5e1d8a2f403"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "examiner_insight",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("syllabus_code", sa.String(8), nullable=False),
        sa.Column("component", sa.String(4), nullable=False),
        sa.Column("exam_series", sa.String(8), nullable=False),
        sa.Column("report_title", sa.String(300), nullable=False),
        sa.Column("question_ref", sa.String(32), nullable=True),
        sa.Column("item_ref", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("pages", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("segment_key", sa.String(48), nullable=False),
        sa.Column("segment_sha", sa.String(64), nullable=False),
        sa.Column("segmenter_version", sa.String(16), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind in ('common_error','what_scored','advice')", name="kind"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"]),
    )
    op.create_index("ix_examiner_insight_tenant_id", "examiner_insight", ["tenant_id"])
    op.create_index("ix_examiner_insight_source_id", "examiner_insight", ["source_id"])
    op.create_index("ix_examiner_insight_subject_id", "examiner_insight", ["subject_id"])
    op.create_index("ix_examiner_insight_item_ref", "examiner_insight", ["item_ref"])


def downgrade() -> None:
    op.drop_table("examiner_insight")
