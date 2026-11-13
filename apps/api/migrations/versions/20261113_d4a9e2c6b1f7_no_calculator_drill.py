"""Non-calculator practice sessions

Revision ID: d4a9e2c6b1f7
Revises: c7f2a1b4e8d3
Create Date: 2026-11-13

- learning_session.no_calculator: a practice session that serves only questions from papers that forbid a
  calculator (0580 Paper 2 from June 2025), like `command_word` narrows a drill to one command word.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a9e2c6b1f7"
down_revision: str | None = "c7f2a1b4e8d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_session",
        sa.Column("no_calculator", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("learning_session", "no_calculator")
