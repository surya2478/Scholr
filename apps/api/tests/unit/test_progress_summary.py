"""Progress aggregation (pure): level counts, focus ordering, recent wins, weekly stats."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.modules.events.service import EventView
from app.modules.mastery.rules import LEVEL_NAMES, MasteryLevel
from app.modules.mastery.schemas import MasteryOut
from app.modules.mistakes.schemas import MistakeOut
from app.modules.progress.service import focus_items, level_counts, recent_wins, subject_progress, week_stats

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)
MATHS, SOCIOLOGY = uuid4(), uuid4()


def row(level: int, *, subject=MATHS, risk: str = "none", days_ago: int | None = 1, code: str = "1.1") -> MasteryOut:  # noqa: ANN001
    return MasteryOut(
        objective_id=uuid4(),
        objective_code=code,
        objective_statement=f"objective {code}",
        subject_id=subject,
        level=level,
        level_name=LEVEL_NAMES[MasteryLevel(level)],
        score=0.5,
        mastery_confidence=0.5,
        evidence_count=3,
        independent_successes=1,
        distinct_days=2,
        last_demonstrated_at=None if days_ago is None else NOW - timedelta(days=days_ago),
        retention_risk=risk,
        rule_version="mastery_v1",
    )


def mistake(severity: str, *, days_ago: int = 1, subject=MATHS, description: str = "sign error") -> MistakeOut:  # noqa: ANN001
    return MistakeOut(
        id=uuid4(),
        subject_id=subject,
        objective_id=uuid4(),
        objective_code="2.1",
        mistake_type="procedural",
        fingerprint="x",
        description=description,
        severity=severity,
        occurrences=2,
        status="open",
        first_seen=NOW - timedelta(days=10),
        last_seen=NOW - timedelta(days=days_ago),
    )


def test_level_counts_fill_unseen_objectives_as_not_introduced() -> None:
    counts = level_counts(5, [row(3), row(4)])
    assert counts["Competent"] == 1 and counts["Mastered"] == 1 and counts["Not introduced"] == 3
    assert sum(counts.values()) == 5


def test_subject_progress_filters_by_subject_and_hides_mastery_without_scope() -> None:
    rows = [row(3), row(1, risk="high"), row(5, subject=SOCIOLOGY)]
    patterns = [mistake("high"), mistake("low"), mistake("high", subject=SOCIOLOGY)]
    maths = subject_progress(
        subject_id=MATHS,
        subject_name="Maths",
        objectives_total=10,
        mastery_rows=rows,
        open_mistakes=patterns,
        include_mastery=True,
    )
    assert (maths.competent_or_better, maths.retention_high, maths.open_mistakes, maths.high_severity_mistakes) == (
        1,
        1,
        2,
        1,
    )
    hidden = subject_progress(
        subject_id=MATHS,
        subject_name="Maths",
        objectives_total=10,
        mastery_rows=rows,
        open_mistakes=patterns,
        include_mastery=False,
    )
    assert hidden.level_counts == {} and hidden.competent_or_better == 0 and hidden.open_mistakes == 2


def test_focus_puts_recent_high_mistakes_before_fading_objectives() -> None:
    old, new = mistake("high", days_ago=5, description="old"), mistake("high", days_ago=1, description="new")
    fading_old, fading_new = row(3, risk="high", days_ago=40, code="9.1"), row(3, risk="high", days_ago=20, code="9.2")
    items = focus_items([fading_new, fading_old, row(4)], [old, mistake("medium"), new])
    assert [i.label for i in items] == ["new", "old", "objective 9.1", "objective 9.2"]
    assert len(focus_items([], [mistake("high") for _ in range(9)])) == 5


def test_recent_wins_need_competent_level_inside_the_window() -> None:
    wins = recent_wins(
        [row(5, days_ago=2), row(3, days_ago=1), row(2, days_ago=1), row(4, days_ago=30)], since=NOW - timedelta(days=7)
    )
    assert [w.level_name for w in wins] == ["Advanced", "Competent"]


def test_week_stats_count_local_days() -> None:
    def ev(kind: str, at: datetime) -> EventView:
        return EventView(
            id=uuid4(), student_id=uuid4(), type=kind, occurred_at=at, subject_id=None, objective_ids=(), payload={}
        )

    late_utc = datetime(2026, 10, 6, 21, tzinfo=UTC)  # already 7 October in Dubai (UTC+4)
    recent = [ev("attempt_evaluated", late_utc), ev("attempt_submitted", NOW), ev("attempt_evaluated", NOW)]
    week = week_stats(
        recent, {"completed": 3, "skipped": 1, "planned": 2}, since=date(2026, 10, 1), timezone="Asia/Dubai"
    )
    assert (week.attempts_evaluated, week.active_days) == (2, 1)
    assert (week.plan_items_total, week.plan_items_completed, week.plan_items_skipped) == (6, 3, 1)
