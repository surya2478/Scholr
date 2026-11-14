"""Exam readiness rule v1 (AC-R2): what it claims, and — more importantly — what it refuses to claim."""

from __future__ import annotations

from app.modules.readiness import rules

AOS = ("AO1", "AO2", "AO3")
WEIGHTS = {"AO1": 0.39, "AO2": 0.39, "AO3": 0.22}


def split(available: float, per_skill: dict[str, float], codes: tuple[str, ...] = AOS) -> rules.MarkSplit:
    return rules.MarkSplit(marks_available=available, per_skill=per_skill, skill_codes=codes)


def test_nothing_is_claimed_without_enough_marks() -> None:
    rows = rules.skill_readiness([split(8, {"AO1": 8, "AO2": 8, "AO3": 8})], skill_codes=AOS, weightings=WEIGHTS)
    assert {r.band for r in rows} == {"unknown"}, "eight marks cannot tell you she is secure"
    assert rules.weighted_share(rows) is None


def test_bands_follow_the_share_once_there_is_enough() -> None:
    strong = [split(10, {"AO1": 8}) for _ in range(3)]  # 24 of 30
    rows = rules.skill_readiness(strong, skill_codes=("AO1",), weightings=WEIGHTS)
    assert rows[0].band == "secure" and rows[0].share == 0.8

    middling = [split(10, {"AO1": 5}) for _ in range(3)]
    assert rules.skill_readiness(middling, skill_codes=("AO1",))[0].band == "developing"

    poor = [split(10, {"AO1": 2}) for _ in range(3)]
    assert rules.skill_readiness(poor, skill_codes=("AO1",))[0].band == "weak"


def test_an_answer_without_a_split_counts_as_coverage_only() -> None:
    """Spreading a whole-question mark across its objectives would invent per-objective evidence."""
    rows = rules.skill_readiness([split(10, {}) for _ in range(4)], skill_codes=AOS, weightings=WEIGHTS)
    for row in rows:
        assert row.answers_seen == 4, "she has met the objective"
        assert row.answers_with_split == 0 and row.share is None, "but nothing is known about how she did"
        assert row.band == "unknown"


def test_only_the_objectives_a_question_carries_are_touched() -> None:
    rows = rules.skill_readiness(
        [split(10, {"AO1": 7}, codes=("AO1", "AO2")) for _ in range(3)], skill_codes=AOS, weightings=WEIGHTS
    )
    by_code = {r.skill_code: r for r in rows}
    assert by_code["AO1"].answers_seen == 3
    assert by_code["AO2"].answers_seen == 3
    assert by_code["AO3"].answers_seen == 0 and by_code["AO3"].band == "unknown"


def test_weighted_share_uses_the_exams_own_weighting() -> None:
    splits = [split(10, {"AO1": 9, "AO2": 5, "AO3": 5}) for _ in range(3)]
    rows = rules.skill_readiness(splits, skill_codes=AOS, weightings=WEIGHTS)
    # AO1 0.9 at weight .39, AO2 0.5 at .39, AO3 0.5 at .22 -> (0.351 + 0.195 + 0.11) / 1.0
    assert rules.weighted_share(rows) == 0.656


def test_weighted_share_renormalises_over_what_can_be_judged() -> None:
    """With only AO1 judged, the answer is AO1's share — not AO1 diluted by two unknowns."""
    splits = [split(10, {"AO1": 8}, codes=("AO1",)) for _ in range(3)]
    rows = rules.skill_readiness(splits, skill_codes=AOS, weightings=WEIGHTS)
    assert rules.weighted_share(rows) == 0.8


def test_shortfall_is_the_gap_to_secure_not_to_the_weighting() -> None:
    rows = rules.skill_readiness([split(10, {"AO1": 5}) for _ in range(3)], skill_codes=("AO1",))
    assert rows[0].shortfall == round(rules.SECURE - 0.5, 4)
    strong = rules.skill_readiness([split(10, {"AO1": 9}) for _ in range(3)], skill_codes=("AO1",))
    assert strong[0].shortfall == 0.0


def test_topic_readiness_is_unknown_until_there_is_evidence() -> None:
    evidence = [
        rules.TopicEvidence("U1", "Research methods", 18, 24, 4, 3, 2),
        rules.TopicEvidence("U2", "Identity", 0, 0, 0, 3, 0),
    ]
    rows = rules.topic_readiness(evidence)
    assert (rows[0].band, rows[0].share) == ("secure", 0.75)
    assert (rows[1].band, rows[1].share) == ("unknown", None)


def test_coverage() -> None:
    assert rules.coverage(3, 6) == 0.5
    assert rules.coverage(0, 0) == 0.0


def test_the_weakest_objective_is_named_only_once_it_can_be_judged() -> None:
    """Improvement 10: never the 'weakest' of objectives nobody has evidence for."""
    nothing = rules.skill_readiness([], skill_codes=AOS, weightings=WEIGHTS)
    assert rules.weakest_skill(nothing) is None
    splits = [split(10, {"AO1": 9, "AO2": 5, "AO3": 3}) for _ in range(3)]
    assert rules.weakest_skill(rules.skill_readiness(splits, skill_codes=AOS, weightings=WEIGHTS)) == "AO3"
    only_ao1 = [split(10, {"AO1": 4}, codes=("AO1",)) for _ in range(3)]
    assert rules.weakest_skill(rules.skill_readiness(only_ao1, skill_codes=AOS, weightings=WEIGHTS)) == "AO1"
