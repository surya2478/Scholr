"""question_item source pages and meta

Revision ID: b5c3d7e9f012
Revises: 9e4b2a6c1d03
Create Date: 2026-09-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b5c3d7e9f012"
down_revision: str | None = "9e4b2a6c1d03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_item",
        sa.Column("source_pages", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "question_item",
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("question_item", "meta")
    op.drop_column("question_item", "source_pages")
