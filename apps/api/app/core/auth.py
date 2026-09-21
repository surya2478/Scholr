"""Bearer-token verification.

- ``AUTH_MODE=dev``: HS256 tokens signed with AUTH_DEV_SECRET, minted by ``app.jobs.dev_token``.
  Settings refuse this mode when APP_ENV=prod.
- ``AUTH_MODE=local`` (docs/STUDENT-APP.md D7): the same HS256 session tokens, issued only by the sign-in
  route after an email and password are checked against the account's stored hash.
- ``AUTH_MODE=jwks``: tokens from the external identity provider, verified against its JWKS with
  issuer and audience checks.

A token only proves who is calling. Role, student record and guardian links always come from the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt

from app.core.config import Settings

DEV_ISSUER = "scholr-dev"
DEV_AUDIENCE = "scholr-api"
LEEWAY_S = 30
MFA_METHODS = frozenset({"mfa", "otp", "hwk", "swk"})


class AuthError(Exception):
    """Token missing, malformed, expired, or not trusted."""


@dataclass(frozen=True)
class VerifiedToken:
    subject: str
    mfa: bool


def issue_dev_token(subject: str, settings: Settings, *, hours: float = 12, mfa: bool = True) -> str:
    if settings.auth_mode != "dev":
        raise AuthError("dev tokens can only be issued when AUTH_MODE=dev")
    return _sign(subject, settings, hours=hours, mfa=mfa)


def issue_session_token(subject: str, settings: Settings, *, hours: float, mfa: bool) -> str:
    """A signed session for an account that has just proved its password (AUTH_MODE=local)."""
    if settings.auth_mode != "local":
        raise AuthError("session tokens can only be issued when AUTH_MODE=local")
    return _sign(subject, settings, hours=hours, mfa=mfa)


def _sign(subject: str, settings: Settings, *, hours: float, mfa: bool) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": DEV_ISSUER,
        "aud": DEV_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    claims["amr"] = ["pwd", "mfa"] if mfa else ["pwd"]
    return jwt.encode(claims, settings.auth_dev_secret.get_secret_value(), algorithm="HS256")


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def verify_token(token: str, settings: Settings) -> VerifiedToken:
    try:
        if settings.auth_mode in {"dev", "local"}:
            claims = jwt.decode(
                token,
                settings.auth_dev_secret.get_secret_value(),
                algorithms=["HS256"],
                audience=DEV_AUDIENCE,
                issuer=DEV_ISSUER,
                leeway=LEEWAY_S,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        else:
            if not (settings.auth_jwks_url and settings.auth_issuer and settings.auth_audience):
                raise AuthError("AUTH_JWKS_URL, AUTH_ISSUER and AUTH_AUDIENCE must all be set")
            key = _jwks_client(settings.auth_jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                audience=settings.auth_audience,
                issuer=settings.auth_issuer,
                leeway=LEEWAY_S,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
    except jwt.PyJWTError as exc:
        raise AuthError(type(exc).__name__) from exc
    amr = claims.get("amr")
    mfa = isinstance(amr, list) and any(method in MFA_METHODS for method in amr)
    return VerifiedToken(subject=str(claims["sub"]), mfa=mfa)
