"""Application settings, loaded from environment / apps/api/.env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]
# The repository's content directory (curriculum, manifests). In a container the code lives alone at /app, with
# content mounted elsewhere, so SCHOLR_CONTENT_DIR names it (infra/docker-compose.home.yml).
CONTENT_DIR = Path(os.environ.get("SCHOLR_CONTENT_DIR") or API_ROOT.parent.parent / "content")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_ROOT / ".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"

    # Runtime connection: non-superuser role so row-level security applies.
    database_url: str
    # Owner connection used only for migrations (DDL).
    migration_database_url: str | None = None
    test_database_url: str | None = None
    test_migration_database_url: str | None = None

    auth_mode: Literal["dev", "local", "jwks"] = "dev"
    auth_dev_secret: SecretStr = SecretStr("")
    auth_jwks_url: str = ""
    auth_issuer: str = ""
    auth_audience: str = ""
    auth_require_guardian_mfa: bool = True
    # AUTH_MODE=local (docs/STUDENT-APP.md D7): email + password accounts signed with AUTH_DEV_SECRET.
    auth_session_hours: float = 12
    auth_login_attempts: int = 8  # consecutive failures before an account is locked out
    auth_lockout_minutes: int = 15

    # Guardian safety notifications (CONTEXT U4: channel not chosen yet). Empty = in-app + audit only.
    notify_webhook_url: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    redis_url: str = "redis://localhost:6379/0"

    subjects_dir: Path = Path("../../subjects")
    private_content_dir: Path = Path("../../content/private")
    uploads_dir: Path = Path("../../content/private/uploads")  # answer photos

    @model_validator(mode="after")
    def _check_prod_safety(self) -> Settings:
        if self.app_env == "prod" and self.auth_mode == "dev":
            raise ValueError("AUTH_MODE=dev is not allowed when APP_ENV=prod")
        if self.auth_mode in {"dev", "local"} and len(self.auth_dev_secret.get_secret_value()) < 32:
            raise ValueError("AUTH_DEV_SECRET must be at least 32 characters")
        return self

    def resolve_path(self, path: Path) -> Path:
        """Resolve a configured path relative to apps/api."""
        return path if path.is_absolute() else (API_ROOT / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
