"""grants for the application runtime role

Revision ID: 9e4b2a6c1d03
Revises: 7d2f1c9b4e01
Create Date: 2026-09-14

The API connects as scholr_app (no superuser, no BYPASSRLS) so row-level security is enforced.
Append-only tables additionally lose UPDATE/DELETE privileges (defence in depth for AC-A4).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "9e4b2a6c1d03"
down_revision: str | None = "7d2f1c9b4e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "scholr_app"
APPEND_ONLY_TABLES = ("learning_event", "audit_log")


def upgrade() -> None:
    revoke = "; ".join(f"REVOKE UPDATE, DELETE ON {t} FROM {APP_ROLE}" for t in APPEND_ONLY_TABLES)
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            RAISE EXCEPTION 'role {APP_ROLE} does not exist; run infra/db-init/02-app-role.sql';
          END IF;
        END
        $$;
        GRANT USAGE ON SCHEMA public TO {APP_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
        REVOKE ALL ON alembic_version FROM {APP_ROLE};
        {revoke};
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE};
        REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};
        REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};
        """
    )
