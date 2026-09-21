"""Date helpers: a small, validated subset of RFC 5545 recurrence rules, and the student's local date."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_SUPPORTED_KEYS = frozenset({"FREQ", "BYDAY", "INTERVAL"})


class RecurrenceError(ValueError):
    pass


def parse_rrule(rule: str) -> frozenset[int]:
    """Weekdays (0 = Monday) on which the rule occurs. Supports FREQ=DAILY and FREQ=WEEKLY;BYDAY=..., INTERVAL=1."""
    parts: dict[str, str] = {}
    for piece in rule.strip().upper().split(";"):
        if not piece:
            continue
        if "=" not in piece:
            raise RecurrenceError(f"malformed rule part: {piece}")
        key, value = piece.split("=", 1)
        parts[key] = value
    if set(parts) - _SUPPORTED_KEYS:
        raise RecurrenceError("only FREQ, BYDAY and INTERVAL are supported")
    if parts.get("INTERVAL", "1") != "1":
        raise RecurrenceError("only INTERVAL=1 is supported")
    if parts.get("FREQ") == "DAILY":
        return frozenset(range(7))
    if parts.get("FREQ") == "WEEKLY":
        days = [d.strip() for d in parts.get("BYDAY", "").split(",") if d.strip()]
        if not days or any(d not in WEEKDAYS for d in days):
            raise RecurrenceError("weekly rules need BYDAY, e.g. BYDAY=MO,WE,FR")
        return frozenset(WEEKDAYS[d] for d in days)
    raise RecurrenceError("only FREQ=DAILY or FREQ=WEEKLY are supported")


def occurs_on(rule: str, day: date) -> bool:
    return day.weekday() in parse_rrule(rule)


def local_date(now: datetime, timezone: str) -> date:
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return now.astimezone(zone).date()


def local_day_start(day: date, timezone: str) -> datetime:
    """Midnight at the start of ``day`` in the student's time zone, as an aware datetime."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.combine(day, time.min, tzinfo=zone)
