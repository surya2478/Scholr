"""Phase 2: goals with derived progress

Revision ID: c5e1d8a2f403
Revises: a3f7b2c8d914
Create Date: 2026-09-16

The `goal` table existed from the initial schema but held only free text, so nothing could be tracked
against it. A goal now names a `measure` Scholr can count, the `target_value` it must reach and the
`baseline_value` it stood at when set — the baseline is what makes a progress bar honest, since without it
"6 of 8 topics" looks like progress even when it started at 6.

`proposed_by_role` and `agreed_at` carry the rule that a goal is set *with* the student: one a parent
proposes stays `proposed` until she agrees to it (AC-G1).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e1d8a2f403"
down_revision: str | None = "a3f7b2c8d914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEASURES = "'topics_secure','active_days_per_week','answers_without_help','open_mistakes'"
STATUSES = "'proposed','active','achieved','dropped'"


def upgrade() -> None:
    # No goal rows exist yet (nothing wrote them), so the new columns can be added NOT NULL directly.
    op.add_column("goal", sa.Column("measure", sa.String(32), nullable=False))
    op.add_column("goal", sa.Column("target_value", sa.Float(), nullable=False))
    op.add_column("goal", sa.Column("baseline_value", sa.Float(), nullable=True))
    op.add_column("goal", sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("goal", sa.Column("proposed_by_role", sa.String(16), nullable=False))
    op.add_column("goal", sa.Column("agreed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("goal", sa.Column("rule_version", sa.String(32), nullable=False))
    op.create_foreign_key("fk_goal_subject_id_subject", "goal", "subject", ["subject_id"], ["id"])
    op.create_check_constraint("measure", "goal", f"measure in ({MEASURES})")
    op.execute("ALTER TABLE goal DROP CONSTRAINT ck_goal_status")
    op.create_check_constraint("status", "goal", f"status in ({STATUSES})")


def downgrade() -> None:
    op.execute("ALTER TABLE goal DROP CONSTRAINT ck_goal_status")
    op.create_check_constraint("status", "goal", "status in ('active','achieved','dropped')")
    op.execute("ALTER TABLE goal DROP CONSTRAINT ck_goal_measure")
    op.drop_constraint("fk_goal_subject_id_subject", "goal", type_="foreignkey")
    for column in (
        "rule_version",
        "agreed_at",
        "proposed_by_role",
        "subject_id",
        "baseline_value",
        "target_value",
        "measure",
    ):
        op.drop_column("goal", column)
