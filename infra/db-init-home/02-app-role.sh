#!/bin/bash
# The application role, with the password from infra/home.env. It is NOT a superuser and has NO BYPASSRLS, so
# row-level security applies to every query the API makes (ARCHITECTURE §6).
set -euo pipefail
: "${SCHOLR_APP_PASSWORD:?SCHOLR_APP_PASSWORD must be set}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'scholr_app') THEN
    CREATE ROLE scholr_app LOGIN PASSWORD '${SCHOLR_APP_PASSWORD}'
      NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  ELSE
    ALTER ROLE scholr_app PASSWORD '${SCHOLR_APP_PASSWORD}';
  END IF;
END
\$\$;
SQL
