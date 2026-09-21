from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.core.auth import issue_dev_token, issue_session_token
from app.core.db import set_rls_context
from app.core.deps import DbDep, PrincipalDep
from app.core.errors import ApiError, not_found
from app.core.rbac import require_role, resolve_student_id
from app.modules.audit import service as audit
from app.modules.identity import accounts, consent, service
from app.modules.identity.schemas import (
    ApproveIn,
    ApproveOut,
    DevSessionIn,
    DevSessionOut,
    MeOut,
    PendingAccountOut,
    RegisterIn,
    RegisterOut,
    RejectIn,
    SignInIn,
    SignInOut,
    StreamChoiceOut,
)
from app.modules.subjects import service as subjects

router = APIRouter(tags=["identity"])


@router.post("/dev/session", response_model=DevSessionOut)
def post_dev_session(body: DevSessionIn, request: Request) -> DevSessionOut:
    """Sign in as a seeded household account while real sign-in is not built yet.

    Only exists when the API runs with AUTH_MODE=dev (config already forbids that in production); anywhere else
    the route reports 404, so no deployment can hand out accounts this way.
    """
    settings = request.app.state.settings
    if settings.auth_mode != "dev" or settings.app_env == "prod":
        raise not_found("route")
    client_host = request.client.host if request.client else None
    if client_host and client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise not_found("route")
    with request.app.state.session_factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")  # identity lookup happens before any user is bound
        subject = service.dev_account_subject(s, body.role)
        name = ""
        if subject is not None:
            principal = service.resolve_principal(s, subject, mfa=True)
            name = principal.display_name if principal else ""
    if subject is None:
        raise not_found("account")
    return DevSessionOut(token=issue_dev_token(subject, settings), role=body.role, display_name=name)


PENDING_MESSAGE = "Thanks — your account is waiting for the admin to approve it. You'll be able to sign in after that."


def _local_only(request: Request) -> None:
    """Email-and-password routes exist only when the API runs with AUTH_MODE=local (D7)."""
    if request.app.state.settings.auth_mode != "local":
        raise not_found("route")


@router.get("/auth/streams", response_model=list[StreamChoiceOut])
def get_auth_streams(request: Request) -> list[StreamChoiceOut]:
    """The streams a registration may ask for, so the sign-up form names no stream of its own (AC-U1)."""
    _local_only(request)
    return [
        StreamChoiceOut(key=stream.key, name=stream.name, status=stream.status)
        for stream in subjects.load_streams().streams
    ]


@router.post("/auth/register", response_model=RegisterOut, status_code=202)
def post_register(body: RegisterIn, request: Request) -> RegisterOut:
    """Register an account. It is `pending` and cannot sign in until an admin approves it."""
    _local_only(request)
    with request.app.state.session_factory() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")  # no caller yet: the account does not exist
        tenant_id = service.default_tenant_id(s)
        if tenant_id is None:
            raise not_found("tenant")
        try:
            accounts.register(
                s,
                tenant_id=tenant_id,
                email=body.email,
                password=body.password,
                display_name=body.display_name,
                requested_streams=body.requested_streams,
                note=body.note,
            )
        except accounts.RegistrationError as exc:
            if exc.code != "email_in_use":
                raise
            # Answered exactly like a new registration: the form must not reveal who already has an account.
            s.rollback()
    return RegisterOut(message=PENDING_MESSAGE)


@router.post("/auth/sign-in", response_model=SignInOut)
def post_sign_in(body: SignInIn, request: Request) -> SignInOut:
    _local_only(request)
    settings = request.app.state.settings
    with request.app.state.session_factory() as s:
        set_rls_context(s, user_id=None, role="system")  # the caller is proving who they are
        try:
            signed_in = accounts.sign_in(s, email=body.email, password=body.password, settings=settings)
        except ApiError:
            s.commit()  # a refusal still counts: the failed attempt and any lockout must be kept
            raise
        s.commit()
    # A password alone is not multi-factor; guardians are refused unless AUTH_REQUIRE_GUARDIAN_MFA is off,
    # which is how the home machine runs until mobile OTP sign-in exists (D7).
    token = issue_session_token(
        signed_in.auth_subject, settings, hours=settings.auth_session_hours, mfa=not settings.auth_require_guardian_mfa
    )
    return SignInOut(
        token=token,
        role=signed_in.role,
        display_name=signed_in.display_name,
        expires_in_hours=settings.auth_session_hours,
    )


@router.get("/admin/registrations", response_model=list[PendingAccountOut])
def get_registrations(principal: PrincipalDep, s: DbDep) -> list[PendingAccountOut]:
    require_role(principal, "admin")
    return [PendingAccountOut(**asdict(account)) for account in accounts.pending_accounts(s)]


@router.post("/admin/registrations/{user_id}/approve", response_model=ApproveOut)
def post_approve_registration(user_id: UUID, body: ApproveIn, principal: PrincipalDep, s: DbDep) -> ApproveOut:
    require_role(principal, "admin")
    enrolled = accounts.approve(
        s,
        user_id=user_id,
        admin_user_id=principal.user_id,
        role=body.role,
        streams=body.streams,
        year_group=body.year_group,
        timezone=body.timezone,
    )
    return ApproveOut(user_id=user_id, role=body.role, streams=body.streams, subjects_enrolled=enrolled)


@router.post("/admin/registrations/{user_id}/reject", status_code=204)
def post_reject_registration(user_id: UUID, body: RejectIn, principal: PrincipalDep, s: DbDep) -> None:
    require_role(principal, "admin")
    accounts.reject(s, user_id=user_id, admin_user_id=principal.user_id, reason=body.reason)


@router.get("/me", response_model=MeOut)
def get_me(principal: PrincipalDep, s: DbDep) -> MeOut:
    return service.me(s, principal)


@router.get("/consents", response_model=list[consent.ConsentOut])
def get_consents(principal: PrincipalDep, s: DbDep, student_id: UUID | None = None) -> list[consent.ConsentOut]:
    sid = resolve_student_id(principal, student_id, scope="progress")
    return consent.list_consents(s, principal, student_id=sid)


@router.post("/consents", response_model=consent.ConsentOut, status_code=201)
def post_consent(
    body: consent.ConsentIn, principal: PrincipalDep, s: DbDep, student_id: UUID | None = None
) -> consent.ConsentOut:
    sid = resolve_student_id(principal, student_id, scope="progress")
    return consent.record_consent(s, principal, body, student_id=sid, now=datetime.now(UTC))


@router.post("/consents/{consent_id}/withdraw", response_model=consent.ConsentOut)
def withdraw_consent(consent_id: UUID, principal: PrincipalDep, s: DbDep) -> consent.ConsentOut:
    return consent.withdraw_consent(s, principal, consent_id, now=datetime.now(UTC))


@router.get("/audit")
def get_audit(
    principal: PrincipalDep, s: DbDep, student_id: UUID | None = None, action: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    require_role(principal, "admin")
    return [asdict(e) for e in audit.list_entries(s, student_id=student_id, action_prefix=action, limit=limit)]
