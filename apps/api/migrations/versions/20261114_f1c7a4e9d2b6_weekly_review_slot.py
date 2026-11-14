"""Weekly check-in for provisional marks

Revision ID: f1c7a4e9d2b6
Revises: e8b3c5d1a7f2
Create Date: 2026-11-14

- student.review_weekday / review_time: when a parent reviews the marks waiting for a check (improvement 9).
  Null means the default, Sunday 18:00 in the student's time zone.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1c7a4e9d2b6"
down_revision: str | None = "e8b3c5d1a7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("student", sa.Column("review_weekday", sa.SmallInteger(), nullable=True))
    op.add_column("student", sa.Column("review_time", sa.Time(), nullable=True))
    op.create_check_constraint(op.f("ck_student_review_weekday"), "student", "review_weekday between 0 and 6")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_student_review_weekday"), "student", type_="check")
    op.drop_column("student", "review_time")
    op.drop_column("student", "review_weekday")
