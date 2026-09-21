"""Phase 2: command-word drills

Revision ID: a3f7b2c8d914
Revises: f1c9a3d5e7b2
Create Date: 2026-09-16

A drill is a practice session narrowed to one command word ("evaluate", "to what extent"), so the question
picker serves only questions that ask for it (AC-R4). Null for every ordinary session.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f7b2c8d914"
down_revision: str | None = "f1c9a3d5e7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("learning_session", sa.Column("command_word", sa.String(32), nullable=True))
    # Command words are stored lower case so a drill can match exactly; the extractor kept the paper's own
    # capitalisation, which made "Describe" and "describe" different words to every reader of the bank.
    op.execute("UPDATE question_item SET command_word = lower(trim(command_word)) WHERE command_word IS NOT NULL")
    op.create_index(
        "ix_question_item_subject_command_word",
        "question_item",
        ["subject_id", "command_word"],
    )


def downgrade() -> None:
    op.drop_index("ix_question_item_subject_command_word", table_name="question_item")
    op.drop_column("learning_session", "command_word")
