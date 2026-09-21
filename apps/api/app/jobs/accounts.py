"""Accounts from the terminal: create the first admin, list pending registrations, approve or reject one.

Usage (from apps/api):
  uv run python -m app.jobs.accounts create-admin --email you@example.com --name "Your Name"
  uv run python -m app.jobs.accounts pending
  uv run python -m app.jobs.accounts approve <email> --role student --streams IGCSE,IIT --year-group "Year 10"
  uv run python -m app.jobs.accounts reject <email> [--reason "..."]

The password is typed at the prompt, never passed as an argument (it would be kept in the shell history) and
never printed. The first admin is created here because approving registrations needs an admin to exist first.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from uuid import uuid4

from sqlalchemy import select

from app.core.db import set_rls_context
from app.core.passwords import WeakPassword, check_strength, hash_password
from app.modules.identity import accounts
from app.modules.identity import service as identity
from app.modules.identity.models import AppUser, UserCredential


def _session():  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.core.db import get_session_factory

    get_settings()
    return get_session_factory()()


def _ask_password(email: str) -> str:
    first = getpass.getpass("Password (at least 10 characters): ")
    if first != getpass.getpass("Repeat the password: "):
        raise SystemExit("the two passwords are not the same")
    try:
        check_strength(first, email=email)
    except WeakPassword as exc:
        raise SystemExit(str(exc)) from exc
    return first


def create_admin(email: str, name: str) -> None:
    address = email.strip().lower()
    password = _ask_password(address)
    with _session() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        tenant_id = identity.default_tenant_id(s)
        if tenant_id is None:
            raise SystemExit("no tenant yet — seed the household first")
        if s.scalar(select(AppUser.id).where(AppUser.email == address)):
            raise SystemExit(f"{address} already has an account")
        user = AppUser(
            tenant_id=tenant_id,
            auth_subject=f"{accounts.LOCAL_SUBJECT_PREFIX}{uuid4()}",
            email=address,
            display_name=name.strip() or address.split("@")[0],
            role="admin",
            status="active",
        )
        s.add(user)
        s.flush()
        s.add(UserCredential(tenant_id=tenant_id, user_id=user.id, password_hash=hash_password(password)))
    print(f"admin account created for {address}")


def show_pending() -> None:
    with _session() as s:
        set_rls_context(s, user_id=None, role="system")
        pending = accounts.pending_accounts(s)
    if not pending:
        print("no registrations waiting")
        return
    for account in pending:
        streams = ", ".join(account.requested_streams) or "-"
        print(f"{account.email:40} {account.display_name:24} asked for {streams:16} {account.requested_at:%Y-%m-%d}")


def _admin_and_user(s, email: str) -> tuple:  # type: ignore[no-untyped-def]
    admin_id = s.scalar(select(AppUser.id).where(AppUser.role == "admin", AppUser.status == "active"))
    if admin_id is None:
        raise SystemExit("no admin account yet — run create-admin first")
    user_id = s.scalar(select(AppUser.id).where(AppUser.email == email.strip().lower()))
    if user_id is None:
        raise SystemExit(f"no account for {email}")
    return admin_id, user_id


def approve(email: str, role: str, streams: list[str], year_group: str) -> None:
    with _session() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        admin_id, user_id = _admin_and_user(s, email)
        enrolled = accounts.approve(
            s, user_id=user_id, admin_user_id=admin_id, role=role, streams=streams, year_group=year_group
        )
    print(f"approved {email} as {role}; enrolled in {', '.join(enrolled) or 'no new subjects'}")


def reject(email: str, reason: str) -> None:
    with _session() as s, s.begin():
        set_rls_context(s, user_id=None, role="system")
        admin_id, user_id = _admin_and_user(s, email)
        accounts.reject(s, user_id=user_id, admin_user_id=admin_id, reason=reason)
    print(f"rejected {email}")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.accounts")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="create the first admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", default="")
    commands.add_parser("pending", help="list registrations waiting for a decision")
    ok = commands.add_parser("approve", help="approve a pending registration")
    ok.add_argument("email")
    ok.add_argument("--role", default="student", choices=["student", "guardian", "admin"])
    ok.add_argument("--streams", default="", help="comma-separated stream keys, e.g. IGCSE,IIT")
    ok.add_argument("--year-group", default="")
    no = commands.add_parser("reject", help="reject a pending registration")
    no.add_argument("email")
    no.add_argument("--reason", default="")
    args = parser.parse_args(argv[1:])
    if args.command == "create-admin":
        create_admin(args.email, args.name)
    elif args.command == "pending":
        show_pending()
    elif args.command == "approve":
        streams = [key.strip() for key in args.streams.split(",") if key.strip()]
        approve(args.email, args.role, streams, args.year_group)
    else:
        reject(args.email, args.reason)


if __name__ == "__main__":
    main(sys.argv)
