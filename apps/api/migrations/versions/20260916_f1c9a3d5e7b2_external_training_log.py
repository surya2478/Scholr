"""Phase 3: external training log and the concept mapping note

Revision ID: f1c9a3d5e7b2
Revises: e6b8d1f4a2c9
Create Date: 2026-09-16

`plan_item` gains the `reinforcement` kind and a `reason_detail` sentence, so a reinforcement item can name
the class it came from instead of a generic template line (AC-X12).

`external_training_log` records a session of the IIT Foundation programme — learning that happens outside
Scholr (docs/PHASE-3.md). It is student data, so it gets the same forced row-level security as every other
student table. `concept.note` explains a mapping where it needs explaining, e.g. where the external course
goes beyond IGCSE and only the ground underneath it is mapped.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1c9a3d5e7b2"
down_revision: str | None = "e6b8d1f4a2c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_TABLES = ("external_training_log",)


KINDS = "'school_topic','revision','mistake_fix','practice','challenge','assessment'"


def upgrade() -> None:
    op.add_column("concept", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("plan_item", sa.Column("reason_detail", sa.String(300), nullable=True))
    op.execute("ALTER TABLE plan_item DROP CONSTRAINT ck_plan_item_kind")
    op.create_check_constraint("kind", "plan_item", f"kind in ({KINDS},'reinforcement')")
    op.create_table(
        "external_training_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("duration_min", sa.SmallInteger(), nullable=True),
        sa.Column(
            "objective_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"
        ),
        sa.Column(
            "weak_objective_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"
        ),
        sa.Column("score", sa.Numeric(7, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(7, 2), nullable=True),
        sa.Column("questions_attempted", sa.SmallInteger(), nullable=True),
        sa.Column("questions_missed", sa.SmallInteger(), nullable=True),
        sa.Column("weaknesses", postgresql.ARRAY(sa.String(120)), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_role", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subject.id"]),
        sa.CheckConstraint("kind in ('class','test','homework','practice')", name="kind"),
        sa.CheckConstraint("duration_min is null or duration_min between 0 and 720", name="duration"),
        sa.CheckConstraint("max_score is null or max_score > 0", name="max_score"),
        sa.CheckConstraint("score is null or score >= 0", name="score"),
        sa.CheckConstraint(
            "questions_attempted is null or questions_missed is null or questions_missed <= questions_attempted",
            name="questions",
        ),
    )
    op.create_index("ix_external_training_log_tenant_id", "external_training_log", ["tenant_id"])
    op.create_index("ix_external_training_log_student_id", "external_training_log", ["student_id"])
    op.create_index("ix_external_training_log_occurred_on", "external_training_log", ["occurred_on"])

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
    op.drop_table("external_training_log")
    op.execute("ALTER TABLE plan_item DROP CONSTRAINT ck_plan_item_kind")
    op.create_check_constraint("kind", "plan_item", f"kind in ({KINDS})")
    op.drop_column("plan_item", "reason_detail")
    op.drop_column("concept", "note")
