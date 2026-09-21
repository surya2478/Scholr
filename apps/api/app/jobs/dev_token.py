"""Mint a development bearer token for a seeded user (AUTH_MODE=dev only).

Usage (from apps/api):
  uv run python -m app.jobs.dev_token <auth_subject> [--hours 12] [--no-mfa]
"""

from __future__ import annotations

import argparse
import sys

from app.core.auth import AuthError, issue_dev_token
from app.core.config import get_settings


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="app.jobs.dev_token")
    parser.add_argument("auth_subject")
    parser.add_argument("--hours", type=float, default=12)
    parser.add_argument("--no-mfa", action="store_true", help="omit the MFA claim (guardians will be refused)")
    args = parser.parse_args(argv[1:])
    try:
        print(issue_dev_token(args.auth_subject, get_settings(), hours=args.hours, mfa=not args.no_mfa))
    except AuthError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main(sys.argv)
