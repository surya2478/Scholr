from datetime import UTC, datetime, timedelta

from app.modules.mastery.rules import EvidenceItem, MasteryLevel, compute_mastery

NOW = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)


def item(days_ago: float, score: float = 1.0, help_level: int = 0, **kw: object) -> EvidenceItem:
    return EvidenceItem(
        occurred_at=NOW - timedelta(days=days_ago),
        score=score,
        help_level=help_level,
        evaluation_confidence=kw.pop("confidence", 0.9),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


def test_no_evidence() -> None:
    assert compute_mastery([], now=NOW).level == MasteryLevel.NOT_INTRODUCED
    assert compute_mastery([], now=NOW, explanation_viewed=True).level == MasteryLevel.INTRODUCED


def test_two_perfect_attempts_are_only_introduced() -> None:
    r = compute_mastery([item(1), item(0.5)], now=NOW)
    assert r.level == MasteryLevel.INTRODUCED
    assert r.independent_successes == 2


def test_developing_with_attempts_but_weak_score() -> None:
    r = compute_mastery([item(3, 0.2), item(2, 0.4), item(1, 0.5)], now=NOW)
    assert r.level == MasteryLevel.DEVELOPING


def test_competent() -> None:
    r = compute_mastery([item(3, 0.5), item(2, 1.0), item(1, 0.9)], now=NOW)
    assert r.level == MasteryLevel.COMPETENT


def test_mastered_requires_distinct_days_and_exam_style() -> None:
    same_day = [item(1.0 + i * 0.01) for i in range(4)]
    assert compute_mastery(same_day, now=NOW).level == MasteryLevel.COMPETENT

    no_exam = [item(3), item(2), item(1), item(0.5)]
    assert compute_mastery(no_exam, now=NOW).level == MasteryLevel.COMPETENT

    ok = [item(3), item(2), item(1, exam_style=True), item(0.5)]
    assert compute_mastery(ok, now=NOW).level == MasteryLevel.MASTERED


def test_open_high_severity_mistake_blocks_mastered() -> None:
    ok = [item(3), item(2), item(1, exam_style=True), item(0.5)]
    r = compute_mastery(ok, now=NOW, has_open_high_severity_mistake=True)
    assert r.level == MasteryLevel.COMPETENT
    assert "held_at_competent_open_high_severity_mistake" in r.reasons


def test_advanced_needs_stretch_successes() -> None:
    ev = [item(4), item(3), item(2, exam_style=True), item(1, stretch=True), item(0.5, stretch=True)]
    assert compute_mastery(ev, now=NOW).level == MasteryLevel.ADVANCED


def test_heavy_help_does_not_count_as_independent() -> None:
    ev = [item(3, help_level=5), item(2, help_level=5), item(1, help_level=4), item(0.5, help_level=5)]
    r = compute_mastery(ev, now=NOW)
    assert r.independent_successes == 0
    assert r.level == MasteryLevel.DEVELOPING
    assert r.score < 0.3


def test_low_confidence_evaluations_are_ignored() -> None:
    ev = [item(3, confidence=0.4), item(2, confidence=0.4), item(1, confidence=0.4)]
    r = compute_mastery(ev, now=NOW, min_evaluation_confidence=0.75)
    assert r.level == MasteryLevel.NOT_INTRODUCED
    assert r.evidence_count == 0


def test_retention_risk() -> None:
    ev = [item(40), item(35), item(30, exam_style=True), item(25)]
    r = compute_mastery(ev, now=NOW)
    assert r.level == MasteryLevel.MASTERED
    assert r.retention_risk == "medium"

    old = [item(70), item(65), item(60, exam_style=True), item(50)]
    assert compute_mastery(old, now=NOW).retention_risk == "high"


def test_failed_retention_check_drops_a_level() -> None:
    ev = [item(30), item(25), item(20, exam_style=True), item(18), item(0.2, score=0.2, retention_check=True)]
    r = compute_mastery(ev, now=NOW)
    assert "failed_retention_check" in r.reasons
    assert r.level == MasteryLevel.COMPETENT


def test_rule_version_recorded() -> None:
    assert compute_mastery([item(1)], now=NOW).rule_version == "default_v1"
