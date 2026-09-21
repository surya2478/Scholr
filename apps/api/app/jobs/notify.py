"""Deliver guardian safety notifications (AC-S3: within 1 minute of a high-severity incident).

Usage (from apps/api):
  uv run python -m app.jobs.notify once           # deliver everything pending, then exit
  uv run python -m app.jobs.notify loop [--every 30]   # keep polling (run beside the API)
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime

import app.models_registry  # noqa: F401
from app.core.config import get_settings
from app.core.db import session_scope
from app.modules.safety.notify import Channel, LogChannel, WebhookChannel, deliver_pending


def channel() -> Channel:
    url = get_settings().notify_webhook_url.get_secret_value()
    return WebhookChannel(url) if url else LogChannel()


def once(ch: Channel) -> None:
    with session_scope(user_id=None, role="system") as s:
        report = deliver_pending(s, ch, now=datetime.now(UTC))
    if report.delivered or report.failed:
        print(f"{datetime.now(UTC):%H:%M:%S} channel={ch.name} delivered={report.delivered} failed={report.failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["once", "loop"])
    parser.add_argument("--every", type=int, default=30, help="seconds between polls (loop)")
    args = parser.parse_args()
    ch = channel()
    if args.command == "once":
        once(ch)
        return
    while True:
        once(ch)
        time.sleep(max(5, args.every))


if __name__ == "__main__":
    main()
