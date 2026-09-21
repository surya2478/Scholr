from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.auth import AuthError, issue_dev_token, verify_token
from app.core.config import Settings

SECRET = "unit-test-secret-" + "x" * 32


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://unused/unused",
        "auth_mode": "dev",
        "auth_dev_secret": SecretStr(SECRET),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_dev_token_round_trip_carries_subject_and_mfa() -> None:
    cfg = settings()
    verified = verify_token(issue_dev_token("test|student", cfg), cfg)
    assert verified.subject == "test|student"
    assert verified.mfa is True


def test_token_without_mfa_claim_is_not_mfa() -> None:
    cfg = settings()
    assert verify_token(issue_dev_token("test|parent", cfg, mfa=False), cfg).mfa is False


def test_expired_token_is_rejected() -> None:
    cfg = settings()
    with pytest.raises(AuthError):
        verify_token(issue_dev_token("test|student", cfg, hours=-1), cfg)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = issue_dev_token("test|student", settings(auth_dev_secret=SecretStr("another-secret-" + "y" * 32)))
    with pytest.raises(AuthError):
        verify_token(token, settings())


def test_garbage_is_rejected() -> None:
    with pytest.raises(AuthError):
        verify_token("not-a-jwt", settings())


def test_jwks_mode_needs_full_configuration_and_refuses_dev_tokens() -> None:
    dev_token = issue_dev_token("test|student", settings())
    jwks = settings(auth_mode="jwks", auth_jwks_url="https://idp.invalid/jwks")
    with pytest.raises(AuthError):
        verify_token(dev_token, jwks)
    with pytest.raises(AuthError):
        issue_dev_token("test|student", jwks)


def test_prod_refuses_dev_auth() -> None:
    with pytest.raises(ValueError):
        settings(app_env="prod")
