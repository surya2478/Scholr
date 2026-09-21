"""FastAPI dependencies: settings, authenticated principal, RLS-bound database sessions, LLM gateway."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import AuthError, verify_token
from app.core.config import Settings
from app.core.db import set_rls_context
from app.core.errors import ApiError, forbidden, unauthorized
from app.core.rbac import Principal
from app.llm.factory import build_gateway
from app.llm.gateway import LLMGateway
from app.llm.recorder import DbCallRecorder
from app.llm.transport import TransportError
from app.modules.audit import service as audit
from app.modules.identity import service as identity


def _settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(_settings)]


def _factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def _bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    # Only the Authorization header. A token in the URL would be written to access logs, proxy logs and browser
    # history; pages that need an authenticated file (lesson audio) fetch it with the header instead.
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    raise unauthorized()


def current_principal(request: Request) -> Principal:
    settings = _settings(request)
    try:
        verified = verify_token(_bearer_token(request), settings)
    except AuthError:
        raise unauthorized("invalid or expired token") from None

    factory = _factory(request)
    with factory() as s, s.begin():
        # Identity tables carry no student RLS, so the lookup runs before any user is bound.
        principal = identity.resolve_principal(s, verified.subject, mfa=verified.mfa)
    if principal is None:
        raise unauthorized("unknown or inactive user")

    if principal.role == "guardian" and settings.auth_require_guardian_mfa and not principal.mfa:
        with factory() as s, s.begin():
            set_rls_context(s, user_id=principal.user_id, role=principal.role)
            audit.record(
                s,
                tenant_id=principal.tenant_id,
                actor_user_id=principal.user_id,
                actor_role=principal.role,
                action="auth.denied_mfa_required",
                entity_type="app_user",
                entity_id=principal.user_id,
            )
        raise forbidden("mfa_required", "guardian accounts must sign in with multi-factor authentication")
    return principal


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def db_session(request: Request, principal: PrincipalDep) -> Iterator[Session]:
    """One transaction per request, with the caller bound for row-level security. Rolls back on error."""
    with _factory(request)() as s, s.begin():
        set_rls_context(s, user_id=principal.user_id, role=principal.role)
        yield s


DbDep = Annotated[Session, Depends(db_session)]


@dataclass(frozen=True)
class RlsSessions:
    """Opens short RLS-bound transactions, so no transaction is held open during an LLM call."""

    factory: sessionmaker[Session]
    principal: Principal

    @contextmanager
    def __call__(self) -> Iterator[Session]:
        with self.factory() as s, s.begin():
            set_rls_context(s, user_id=self.principal.user_id, role=self.principal.role)
            yield s


def rls_sessions(request: Request, principal: PrincipalDep) -> RlsSessions:
    return RlsSessions(_factory(request), principal)


SessionsDep = Annotated[RlsSessions, Depends(rls_sessions)]


def llm_gateway(request: Request) -> LLMGateway:
    """The app's gateway, built on first use so the API runs (without AI features) when no key is configured."""
    app = request.app
    if app.state.gateway is None:
        try:
            app.state.gateway = build_gateway(DbCallRecorder(app.state.session_factory))
        except TransportError:
            raise ApiError(503, "llm_unavailable", "AI features are not configured on this server.") from None
    return app.state.gateway
