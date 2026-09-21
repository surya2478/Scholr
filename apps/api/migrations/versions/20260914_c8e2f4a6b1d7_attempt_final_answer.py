"""attempt final answer and transcription metadata

Revision ID: c8e2f4a6b1d7
Revises: b5c3d7e9f012
Create Date: 2026-09-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8e2f4a6b1d7"
down_revision: str | None = "b5c3d7e9f012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attempt", sa.Column("final_answer", sa.Text(), nullable=True))
    op.add_column(
        "attempt",
        sa.Column("transcription_meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("attempt", "transcription_meta")
    op.drop_column("attempt", "final_answer")
