"""Spaced mistake repair

Revision ID: e8b3c5d1a7f2
Revises: d4a9e2c6b1f7
Create Date: 2026-11-14

- mistake_pattern.due_on: when to try the mistake again (the day after it, then three days after the first repair).
- mistake_pattern.resolved_on: the day it closed, for the "fixed this month" ledger.
Both are projections from learning_event, filled by `python -m app.jobs.mistakes rebuild`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8b3c5d1a7f2"
down_revision: str | None = "d4a9e2c6b1f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mistake_pattern", sa.Column("due_on", sa.Date(), nullable=True))
    op.add_column("mistake_pattern", sa.Column("resolved_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("mistake_pattern", "resolved_on")
    op.drop_column("mistake_pattern", "due_on")
