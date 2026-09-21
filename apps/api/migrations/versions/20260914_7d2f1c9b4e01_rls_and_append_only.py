"""row-level security and append-only tables

Revision ID: 7d2f1c9b4e01
Revises: 3b34158a2a06
Create Date: 2026-09-14

Every table holding a student's data gets FORCE ROW LEVEL SECURITY so even the owning
database role is filtered. The acting user is bound per transaction via
set_config('scholr.user_id'/'scholr.role', ..., true) — see app.core.db.set_rls_context.

The table lists below are frozen for this revision. tests/unit/test_rls_coverage.py fails
if a model with student_id is added without a follow-up migration.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "7d2f1c9b4e01"
down_revision: str | None = "3b34158a2a06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STUDENT_TABLES = (
    "assessment",
    "attempt",
    "availability",
    "commitment",
    "consent_record",
    "conversation",
    "enrollment",
    "evaluation",
    "goal",
    "learning_event",
    "learning_memory",
    "learning_session",
    "mastery_state",
    "message",
    "mistake_occurrence",
    "mistake_pattern",
    "plan_item",
    "safety_incident",
    "school_result",
    "skill_profile",
    "study_assignment",
    "study_plan",
    "teaching_plan_entry",
    "upcoming_assessment",
)
NULLABLE_STUDENT_TABLES = ("retrieval_log",)
SYSTEM_READ_TABLES = ("audit_log", "llm_call")
APPEND_ONLY_TABLES = ("learning_event", "audit_log")


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION scholr_current_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('scholr.user_id', true), '')::uuid $$;

        CREATE OR REPLACE FUNCTION scholr_current_role() RETURNS text
        LANGUAGE sql STABLE AS $$ SELECT coalesce(nullif(current_setting('scholr.role', true), ''), 'none') $$;

        CREATE OR REPLACE FUNCTION scholr_can_access_student(sid uuid) RETURNS boolean
        LANGUAGE sql STABLE AS $$
          SELECT CASE scholr_current_role()
            WHEN 'system' THEN true
            WHEN 'admin' THEN true
            WHEN 'student' THEN EXISTS (
              SELECT 1 FROM student s WHERE s.id = sid AND s.user_id = scholr_current_user_id())
            WHEN 'guardian' THEN EXISTS (
              SELECT 1 FROM guardian_student_link l JOIN guardian g ON g.id = l.guardian_id
              WHERE l.student_id = sid AND l.revoked_at IS NULL AND g.user_id = scholr_current_user_id())
            ELSE false
          END
        $$;

        CREATE OR REPLACE FUNCTION scholr_reject_modification() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
        END
        $$;
        """
    )

    for table in STUDENT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_student_access ON {table} "
            "USING (scholr_can_access_student(student_id)) "
            "WITH CHECK (scholr_can_access_student(student_id))"
        )

    for table in NULLABLE_STUDENT_TABLES:
        condition = (
            "CASE WHEN student_id IS NULL THEN scholr_current_role() IN ('system','admin') "
            "ELSE scholr_can_access_student(student_id) END"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_access ON {table} USING ({condition}) WITH CHECK ({condition})")

    for table in SYSTEM_READ_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_read ON {table} FOR SELECT USING (scholr_current_role() IN ('system','admin'))"
        )
        op.execute(f"CREATE POLICY {table}_insert ON {table} FOR INSERT WITH CHECK (scholr_current_role() <> 'none')")

    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION scholr_reject_modification()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    for table in SYSTEM_READ_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_read ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in NULLABLE_STUDENT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_access ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in STUDENT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_student_access ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DROP FUNCTION IF EXISTS scholr_reject_modification();
        DROP FUNCTION IF EXISTS scholr_can_access_student(uuid);
        DROP FUNCTION IF EXISTS scholr_current_role();
        DROP FUNCTION IF EXISTS scholr_current_user_id();
        """
    )
