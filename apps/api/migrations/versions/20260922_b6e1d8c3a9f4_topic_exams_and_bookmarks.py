"""Topic exams and question bookmarks

Revision ID: b6e1d8c3a9f4
Revises: a1c7e5d20b43
Create Date: 2026-09-22

- assessment.kind gains 'topic_exam': a test set from chosen topics. It is sat under exam conditions but is not a
  past-paper sitting, so mastery does not weigh it as exam evidence (review of 22 Sep 2026).
- question_bookmark: questions she saved to revise, moved from the browser's storage to her record so they follow
  her across devices. Student data, so forced row-level security.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6e1d8c3a9f4"
down_revision: str | None = "a1c7e5d20b43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_TABLES = ("question_bookmark",)
OLD_KINDS = "'practice','quiz','baseline','post','retention','exam_style'"
NEW_KINDS = OLD_KINDS + ",'topic_exam'"


def upgrade() -> None:
    op.execute("ALTER TABLE assessment DROP CONSTRAINT ck_assessment_kind")
    op.execute(f"ALTER TABLE assessment ADD CONSTRAINT ck_assessment_kind CHECK (kind in ({NEW_KINDS}))")

    op.create_table(
        "question_bookmark",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(16), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "question_item_id"),
        sa.CheckConstraint(
            "tag in ('examiner_trap','calc_heavy','must_revise')", name=op.f("ck_question_bookmark_tag")
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_item_id"], ["question_item.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_question_bookmark_tenant_id", "question_bookmark", ["tenant_id"])
    op.create_index("ix_question_bookmark_student_id", "question_bookmark", ["student_id"])
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
    op.drop_table("question_bookmark")
    # Her topic exams are her record: refuse rather than delete them.
    if op.get_bind().execute(sa.text("SELECT 1 FROM assessment WHERE kind = 'topic_exam' LIMIT 1")).first():
        raise RuntimeError("topic exams exist; they are student records and are not deleted by a downgrade")
    op.execute("ALTER TABLE assessment DROP CONSTRAINT ck_assessment_kind")
    op.execute(f"ALTER TABLE assessment ADD CONSTRAINT ck_assessment_kind CHECK (kind in ({OLD_KINDS}))")
