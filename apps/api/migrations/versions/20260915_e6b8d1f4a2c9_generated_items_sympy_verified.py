"""AC-E1: template/generated items can be verified only when SymPy verified their answer

Revision ID: e6b8d1f4a2c9
Revises: d4a7c2e9b3f1
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e6b8d1f4a2c9"
down_revision: str | None = "d4a7c2e9b3f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONDITION = (
    "origin not in ('template','generated') OR verification_status <> 'verified' "
    "OR coalesce((answer_spec ->> 'sympy_verified')::boolean, false)"
)


def upgrade() -> None:
    op.create_check_constraint("generated_needs_sympy_verification", "question_item", CONDITION)


def downgrade() -> None:
    op.drop_constraint("ck_question_item_generated_needs_sympy_verification", "question_item", type_="check")
