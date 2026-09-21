"""Study Critic rule v1 (AC-C1, AC-C2): what fires, what stays quiet, and what it is allowed to say."""

from __future__ import annotations

import re
from datetime import date, timedelta

import yaml

from app.modules.critic import rules
from app.modules.critic.service import PATTERNS_FILE, templates

START = date(2026, 9, 1)  # a Tuesday


def day(offset: int, **kw: int) -> rules.DayActivity:
    fields = {
        "study_minutes": 0,
        "answers": 0,
        "answers_with_help": 0,
        "plan_items": 0,
        "plan_items_done": 0,
        **kw,
    }
    return rules.DayActivity(day=START + timedelta(days=offset), **fields)  # type: ignore[arg-type]


def test_a_quiet_month_is_not_a_pattern() -> None:
    """Silence is the commonest input. It must produce nothing rather than five worried observations."""
    assert rules.patterns([day(i) for i in range(28)], []) == []


def test_steady_study_is_not_a_pattern() -> None:
    days = [day(i, study_minutes=40, answers=2, plan_items=2, plan_items_done=2) for i in range(28)]
    subjects = [rules.SubjectActivity("a", "Maths", 600), rules.SubjectActivity("b", "Sociology", 520)]
    assert rules.patterns(days, subjects) == []


def test_inconsistency_needs_repeated_gaps_not_one() -> None:
    one_gap = [day(i, study_minutes=30) for i in (0, 1, 2, 3, 4, 5, 12)]
    assert rules.inconsistency(one_gap) is None

    two_gaps = [day(i, study_minutes=30) for i in (0, 1, 2, 9, 10, 11, 20)]
    pattern = rules.inconsistency(two_gaps)
    assert pattern is not None
    assert pattern.facts["gaps"] == 2 and pattern.facts["longest_gap"] == 9


def test_inconsistency_stays_quiet_until_there_is_a_habit() -> None:
    barely = [day(i, study_minutes=30) for i in (0, 7, 14)]
    assert rules.inconsistency(barely) is None, "three study days is not enough to call someone inconsistent"


def test_cramming_is_one_day_carrying_the_week() -> None:
    days = []
    for week in range(3):
        days.append(day(week * 7, study_minutes=200))
        days.append(day(week * 7 + 1, study_minutes=20))
    pattern = rules.cramming(days)
    assert pattern is not None
    assert pattern.facts["weeks"] == 3 and pattern.severity == "watch"


def test_a_single_study_day_in_a_week_is_not_cramming() -> None:
    """One session in a week is 100% of that week, but calling it cramming would be nonsense."""
    days = [day(week * 7, study_minutes=60) for week in range(4)]
    assert rules.cramming(days) is None


def test_unrealistic_plan_counts_finished_against_planned() -> None:
    days = []
    for week in range(2):
        days.append(day(week * 7, plan_items=6, plan_items_done=1))
    pattern = rules.unrealistic_plan(days)
    assert pattern is not None
    assert pattern.facts == {"weeks": 2, "planned": 12, "finished": 2}


def test_a_small_plan_missed_is_not_a_pattern() -> None:
    days = [day(week * 7, plan_items=2, plan_items_done=0) for week in range(4)]
    assert rules.unrealistic_plan(days) is None


def test_help_dependency_compares_the_halves_of_the_window() -> None:
    days = [day(i, answers=2, answers_with_help=0) for i in range(14)]
    days += [day(14 + i, answers=2, answers_with_help=2) for i in range(14)]
    pattern = rules.help_dependency(days)
    assert pattern is not None
    assert pattern.facts["before"] == 0 and pattern.facts["after"] == 100


def test_help_dependency_ignores_a_thin_window() -> None:
    days = [day(i, answers=1, answers_with_help=1) for i in (0, 20)]
    assert rules.help_dependency(days) is None


def test_help_falling_is_never_reported_as_dependency() -> None:
    days = [day(i, answers=3, answers_with_help=3) for i in range(14)]
    days += [day(14 + i, answers=3, answers_with_help=0) for i in range(14)]
    assert rules.help_dependency(days) is None


def test_subject_imbalance_names_the_quiet_subject() -> None:
    subjects = [rules.SubjectActivity("a", "Maths", 900), rules.SubjectActivity("b", "Sociology", 60)]
    pattern = rules.subject_imbalance(subjects)
    assert pattern is not None
    assert pattern.facts["subject"] == "Sociology" and pattern.facts["minutes"] == 60


def test_subject_imbalance_waits_for_enough_study_to_divide() -> None:
    thin = [rules.SubjectActivity("a", "Maths", 60), rules.SubjectActivity("b", "Sociology", 0)]
    assert rules.subject_imbalance(thin) is None


def test_one_subject_cannot_be_imbalanced() -> None:
    assert rules.subject_imbalance([rules.SubjectActivity("a", "Maths", 600)]) is None


# --- what the critic is allowed to say -------------------------------------------------------------------

# Words that turn an observation into a verdict on the child. A pattern says what happened, not what she is.
FORBIDDEN = re.compile(
    r"\b(lazy|lazily|struggling|struggles|unmotivated|motivation|careless|weak student|poor|bad habit|"
    r"disorganised|undisciplined|failing|falling behind|should be ashamed|worry|worried)\b",
    re.I,
)


def test_no_template_diagnoses_the_student() -> None:  # AC-C2
    data = yaml.safe_load(PATTERNS_FILE.read_text(encoding="utf-8"))
    for kind, template in data["patterns"].items():
        for field in ("title", "student", "guardian", "why"):
            offending = FORBIDDEN.findall(template[field])
            assert not offending, f"{kind}.{field} passes judgement: {offending}"


def test_every_pattern_has_both_voices_and_they_carry_the_numbers() -> None:
    data = templates()
    for kind, template in data["patterns"].items():
        assert template["student"] and template["guardian"] and template["why"], kind
        # Each voice must interpolate at least one fact, or it is a slogan rather than an observation.
        assert "{" in template["student"], f"{kind} student line cites no numbers"
        assert "{" in template["guardian"], f"{kind} guardian line cites no numbers"


def test_every_rule_kind_has_wording() -> None:
    """A pattern with no template would crash the moment it first fired on real data."""
    kinds = {"inconsistency", "cramming", "unrealistic_plan", "help_dependency", "subject_imbalance"}
    assert set(templates()["patterns"]) == kinds
