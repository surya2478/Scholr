"""learning_session.memory_summarized_at (learning memory job bookkeeping)

Revision ID: d4a7c2e9b3f1
Revises: c8e2f4a6b1d7
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7c2e9b3f1"
down_revision: str | None = "c8e2f4a6b1d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("learning_session", sa.Column("memory_summarized_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("learning_session", "memory_summarized_at")
