"""Local accounts: register with an email, sign in with a password, and wait for an admin (D7).

The rules, in one place, because they decide who may use the app at all:

- registering creates an account with status ``pending``: it has a password but no student record, no
  enrollments and no token. Nothing about the student is visible to it;
- an admin approves it, choosing the role and the streams it may see; approval creates the student record
  (students) and enrolls them in every subject of each granted stream;
- signing in is refused while an account is pending, rejected or disabled, and after
  ``auth_login_attempts`` consecutive wrong passwords until ``auth_lockout_minutes`` have passed;
- a wrong email and a wrong password are answered the same way, so the form never says who has an account.

Every decision is audit-logged. Passwords are never logged, returned or compared outside ``core.passwords``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import passwords
from app.core.config import Settings
from app.core.errors import ApiError, forbidden, unauthorized
from app.modules.audit import service as audit
from app.modules.curriculum import service as curriculum
from app.modules.enrollment import service as enrollment
from app.modules.identity.models import AppUser, RegistrationRequest, Student, UserCredential
from app.modules.subjects import config as subject_config

SELF_SERVICE_ROLE = "student"  # what a registration may become without the admin choosing otherwise
LOCAL_SUBJECT_PREFIX = "local|"


class RegistrationError(ApiError):
    """The details given cannot be registered (bad email, weak password, address already used)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


@dataclass(frozen=True)
class PendingAccount:
    user_id: UUID
    email: str
    display_name: str
    requested_streams: list[str]
    note: str
    requested_at: datetime


def _normalise_email(email: str) -> str:
    cleaned = email.strip().lower()
    local, _, domain = cleaned.partition("@")
    if not local or "." not in domain or " " in cleaned:
        raise RegistrationError("invalid_email", "that does not look like an email address")
    return cleaned


def known_streams() -> list[str]:
    return [stream.key for stream in subject_config.load_streams().streams]


def register(
    s: Session,
    *,
    tenant_id: UUID,
    email: str,
    password: str,
    display_name: str,
    requested_streams: list[str],
    note: str = "",
) -> UUID:
    """Create a pending account. It cannot sign in until an admin approves it."""
    address = _normalise_email(email)
    try:
        passwords.check_strength(password, email=address)
    except passwords.WeakPassword as exc:
        raise RegistrationError("weak_password", str(exc)) from exc
    known = known_streams()
    unknown = [key for key in requested_streams if key not in known]
    if unknown:
        raise RegistrationError("unknown_stream", f"no such stream: {', '.join(unknown)}")
    if s.scalar(select(AppUser.id).where(AppUser.email == address)):
        # An address already in use is answered as success by the route, so the form cannot be used to find out
        # who has an account; the duplicate simply never becomes a second request.
        raise RegistrationError("email_in_use", "that address is already registered")
    user = AppUser(
        tenant_id=tenant_id,
        auth_subject=f"{LOCAL_SUBJECT_PREFIX}{uuid4()}",
        email=address,
        display_name=display_name.strip()[:200] or address.split("@")[0],
        role=SELF_SERVICE_ROLE,
        status="pending",
    )
    s.add(user)
    s.flush()
    s.add(UserCredential(tenant_id=tenant_id, user_id=user.id, password_hash=passwords.hash_password(password)))
    s.add(
        RegistrationRequest(
            tenant_id=tenant_id,
            user_id=user.id,
            requested_streams=list(dict.fromkeys(requested_streams)),
            note=note.strip()[:500],
        )
    )
    audit.record(
        s,
        tenant_id=tenant_id,
        actor_user_id=user.id,
        actor_role="anonymous",
        action="auth.registered",
        entity_type="app_user",
        entity_id=user.id,
        meta={"streams": requested_streams},
    )
    return user.id


@dataclass(frozen=True)
class SignedIn:
    user_id: UUID
    auth_subject: str
    role: str
    display_name: str


def sign_in(s: Session, *, email: str, password: str, settings: Settings, now: datetime | None = None) -> SignedIn:
    """Check an email and password. Raises 401 for anything wrong, 403 while the account waits for an admin."""
    now = now or datetime.now(UTC)
    address = email.strip().lower()
    row = s.execute(
        select(AppUser, UserCredential)
        .join(UserCredential, UserCredential.user_id == AppUser.id)
        .where(AppUser.email == address)
    ).one_or_none()
    if row is None:
        passwords.hash_password(password)  # same work as a real check, so timing does not reveal the address
        raise unauthorized("email or password is wrong")
    user, credential = row
    if credential.locked_until and credential.locked_until > now:
        raise forbidden("account_locked", "too many wrong passwords — try again later")
    if not passwords.verify_password(credential.password_hash, password):
        credential.failed_attempts += 1
        if credential.failed_attempts >= settings.auth_login_attempts:
            credential.locked_until = now + timedelta(minutes=settings.auth_lockout_minutes)
            credential.failed_attempts = 0
            audit.record(
                s,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                actor_role=user.role,
                action="auth.locked_out",
                entity_type="app_user",
                entity_id=user.id,
            )
        raise unauthorized("email or password is wrong")
    credential.failed_attempts = 0
    credential.locked_until = None
    if user.status == "pending":
        raise forbidden("approval_pending", "your account is waiting for the admin to approve it")
    if user.status != "active":
        raise forbidden("account_not_active", "this account cannot sign in")
    credential.last_sign_in_at = now
    if passwords.needs_rehash(credential.password_hash):
        credential.password_hash = passwords.hash_password(password)
    audit.record(
        s,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        actor_role=user.role,
        action="auth.signed_in",
        entity_type="app_user",
        entity_id=user.id,
    )
    return SignedIn(user.id, user.auth_subject, user.role, user.display_name)


def pending_accounts(s: Session) -> list[PendingAccount]:
    rows = s.execute(
        select(AppUser, RegistrationRequest)
        .join(RegistrationRequest, RegistrationRequest.user_id == AppUser.id)
        .where(RegistrationRequest.decision == "pending")
        .order_by(RegistrationRequest.created_at)
    ).all()
    return [
        PendingAccount(
            user_id=user.id,
            email=user.email or "",
            display_name=user.display_name,
            requested_streams=list(request.requested_streams),
            note=request.note,
            requested_at=request.created_at,
        )
        for user, request in rows
    ]


def approve(
    s: Session,
    *,
    user_id: UUID,
    admin_user_id: UUID,
    role: str,
    streams: list[str],
    year_group: str = "",
    timezone: str = "Asia/Dubai",
    now: datetime | None = None,
) -> list[str]:
    """Activate a pending account and give it the granted streams. Returns the subject codes enrolled."""
    now = now or datetime.now(UTC)
    user, request = _pending(s, user_id)
    unknown = [key for key in streams if key not in known_streams()]
    if unknown:
        raise RegistrationError("unknown_stream", f"no such stream: {', '.join(unknown)}")
    if role not in {"student", "guardian", "admin"}:
        raise RegistrationError("unknown_role", f"no such role: {role}")
    user.role = role
    user.status = "active"
    request.decision = "approved"
    request.granted_streams = list(dict.fromkeys(streams))
    request.decided_by = admin_user_id
    request.decided_at = now
    enrolled: list[str] = []
    if role == "student":
        student = s.scalar(select(Student).where(Student.user_id == user.id))
        if student is None:
            student = Student(
                tenant_id=user.tenant_id,
                user_id=user.id,
                display_name=user.display_name,
                year_group=year_group or "",
                timezone=timezone,
            )
            s.add(student)
            s.flush()
        enrolled = grant_streams(s, student_id=student.id, tenant_id=user.tenant_id, streams=request.granted_streams)
    audit.record(
        s,
        tenant_id=user.tenant_id,
        actor_user_id=admin_user_id,
        actor_role="admin",
        action="auth.registration_approved",
        entity_type="app_user",
        entity_id=user.id,
        meta={"role": role, "streams": request.granted_streams, "subjects": enrolled},
    )
    return enrolled


def reject(s: Session, *, user_id: UUID, admin_user_id: UUID, reason: str = "", now: datetime | None = None) -> None:
    user, request = _pending(s, user_id)
    user.status = "rejected"
    request.decision = "rejected"
    request.decided_by = admin_user_id
    request.decided_at = now or datetime.now(UTC)
    request.reason = reason.strip()[:500]
    audit.record(
        s,
        tenant_id=user.tenant_id,
        actor_user_id=admin_user_id,
        actor_role="admin",
        action="auth.registration_rejected",
        entity_type="app_user",
        entity_id=user.id,
    )


def grant_streams(s: Session, *, student_id: UUID, tenant_id: UUID, streams: list[str]) -> list[str]:
    """Enroll a student in every subject of the given streams; returns the subject codes actually added."""
    by_code = {row.code: row.id for row in curriculum.list_subject_summaries(s)}
    wanted = [
        by_code[config.subject_code]
        for key in streams
        for config in subject_config.subjects_in_stream(key)
        if config.subject_code in by_code
    ]
    added = set(enrollment.enroll_in_subjects(s, tenant_id=tenant_id, student_id=student_id, subject_ids=wanted))
    return [code for code, subject_id in by_code.items() if subject_id in added]


def _pending(s: Session, user_id: UUID) -> tuple[AppUser, RegistrationRequest]:
    row = s.execute(
        select(AppUser, RegistrationRequest)
        .join(RegistrationRequest, RegistrationRequest.user_id == AppUser.id)
        .where(AppUser.id == user_id)
    ).one_or_none()
    if row is None:
        raise RegistrationError("no_request", "that account has no registration request")
    user, request = row
    if request.decision != "pending":
        raise RegistrationError("already_decided", f"that request was already {request.decision}")
    return user, request
