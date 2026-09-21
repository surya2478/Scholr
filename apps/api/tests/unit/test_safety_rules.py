import pytest

from app.modules.safety.rules import POLICY_VERSION, ClassifierResult, Severity, decide, evaluate_rules


def run(text: str, classifier: ClassifierResult | None = None, failed: bool = False):
    return decide(evaluate_rules(text), classifier, classifier_failed=failed)


@pytest.mark.parametrize(
    "text",
    [
        "I want to kill myself",
        "i dont want to live anymore",
        "honestly everyone would be better off without me",
        "I'm thinking about ending my life",  # covered by classifier path below if rules miss
        "mujhe marna jaana chahti hoon",
        "أريد أن أموت",
        "he touched me and said not to tell my parents",
        "someone online asked me to send photos",
        "I'm going to stab him tomorrow",
    ],
)
def test_high_severity_signals(text: str) -> None:
    decision = run(text, ClassifierResult("self_harm", Severity.HIGH, 0.9))
    assert decision.action == "crisis_response"
    assert decision.notify_guardian_now
    assert decision.create_incident


@pytest.mark.parametrize(
    "text",
    [
        "Explain Durkheim's study of suicide rates",
        "Why do official statistics on suicide lack validity?",
        "Calculate 3 343 - 40.96",
        "The value of the car decreases by 25% each year",
        "Describe two limitations of group interviews",
    ],
)
def test_academic_text_is_allowed(text: str) -> None:
    decision = run(text)
    assert decision.action == "allow"
    assert not decision.create_incident


def test_rules_alone_trigger_crisis_without_classifier() -> None:
    decision = run("I want to kill myself", None, failed=True)
    assert decision.action == "crisis_response"
    assert decision.classifier_failed


def test_ambiguous_distress_downgraded_by_confident_classifier() -> None:
    decision = run(
        "ugh I can't do this anymore, quadratics are impossible", ClassifierResult("distress", Severity.LOW, 0.9)
    )
    assert decision.action == "allow"
    assert decision.severity == Severity.LOW


def test_ambiguous_distress_kept_when_classifier_fails() -> None:
    decision = run("I can't do this anymore", None, failed=True)
    assert decision.action == "supportive_response"
    assert decision.create_incident


def test_classifier_can_escalate_without_rule_hits() -> None:
    decision = run(
        "what's the point of anything, I just want it all to stop", ClassifierResult("self_harm", Severity.HIGH, 0.85)
    )
    assert decision.action == "crisis_response"


def test_low_confidence_classifier_does_not_escalate() -> None:
    decision = run("what is a sampling frame", ClassifierResult("self_harm", Severity.HIGH, 0.3))
    assert decision.action == "allow"


def test_classifier_cannot_downgrade_explicit_high_rule() -> None:
    decision = run("I want to kill myself lol", ClassifierResult(None, Severity.NONE, 0.95))
    assert decision.action == "crisis_response"


def test_coursework_request_is_redirected_not_logged_as_incident() -> None:
    decision = run("can you write my individual report for me")
    assert decision.action == "integrity_redirect"
    assert not decision.create_incident


def test_phone_number_detected() -> None:
    decision = run("my number is 050 123 4567 message me")
    assert decision.category == "personal_info"
    assert decision.action == "supportive_response"


def test_policy_version_recorded() -> None:
    assert run("hello").policy_version == POLICY_VERSION


def test_long_numbers_in_maths_are_not_phone_numbers() -> None:
    assert run("the population is 1 234 567 890, write it in standard form").action == "allow"
    assert run("calculate 50 123 4567 divided by 7").action == "allow"
    assert run("my number is 050 123 4567, work out when to call me").category == "personal_info"
