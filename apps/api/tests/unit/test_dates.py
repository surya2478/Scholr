def test_weekly_check_in_times_in_her_time_zone() -> None:
    from datetime import UTC, datetime, time

    from app.tools.dates import last_weekly, next_weekly

    sunday_six = (6, time(18, 0))  # Sundays 18:00, Dubai (UTC+4)
    sat = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)  # Saturday 14:00 in Dubai
    assert next_weekly(sat, *sunday_six, "Asia/Dubai").isoformat() == "2026-11-15T18:00:00+04:00"
    assert last_weekly(sat, *sunday_six, "Asia/Dubai").isoformat() == "2026-11-08T18:00:00+04:00"
    on_time = datetime(2026, 11, 15, 14, 0, tzinfo=UTC)  # exactly Sunday 18:00 in Dubai
    assert last_weekly(on_time, *sunday_six, "Asia/Dubai").isoformat() == "2026-11-15T18:00:00+04:00"
    assert next_weekly(on_time, *sunday_six, "Asia/Dubai").isoformat() == "2026-11-22T18:00:00+04:00"
