-- Application runtime role. NOT a superuser and NO BYPASSRLS, so row-level security applies.
-- Migrations run as the owner role (scholr); the API connects as scholr_app.
-- Dev password only — production uses a secret-managed password.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'scholr_app') THEN
    CREATE ROLE scholr_app LOGIN PASSWORD 'scholr_app_dev_password'
      NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END
$$;
