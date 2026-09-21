from __future__ import annotations

import pytest

from app.modules.safety.rules import SafetyDecision, Severity
from app.modules.safety.schemas import CrisisResource
from app.modules.safety.service import load_policy, output_issues, response_for


def decision(action: str, category: str | None = None, severity: Severity = Severity.MEDIUM) -> SafetyDecision:
    return SafetyDecision(
        action=action,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        severity=severity,
        create_incident=True,
        notify_guardian_now=severity >= Severity.HIGH,
        policy_version="safety_v1",
        rule_ids=(),
        classifier_used=False,
        classifier_failed=False,
    )


def test_policy_file_has_a_template_for_every_blocking_action() -> None:
    policy = load_policy()
    for key in ("crisis_response", "supportive_response", "integrity_redirect", "personal_info"):
        assert policy.responses[key].strip()


def test_allow_has_no_response_and_personal_info_gets_its_own_template() -> None:
    policy = load_policy()
    assert response_for(decision("allow", severity=Severity.NONE)) is None
    assert response_for(decision("supportive_response", "personal_info")) == policy.responses["personal_info"]
    assert response_for(decision("supportive_response", "bullying")) == policy.responses["supportive_response"]


def test_unverified_crisis_resources_are_never_shown() -> None:
    policy = load_policy()
    listed = policy.model_copy(
        update={
            "crisis_resources": policy.crisis_resources.model_copy(
                update={"verified": False, "entries": [CrisisResource(name="Line", contact="000", region="X")]}
            )
        }
    )
    assert "000" not in (response_for(decision("crisis_response", "self_harm", Severity.HIGH), listed) or "")
    verified = listed.model_copy(
        update={"crisis_resources": listed.crisis_resources.model_copy(update={"verified": True})}
    )
    assert "Line: 000 (X)" in (response_for(decision("crisis_response", "self_harm", Severity.HIGH), verified) or "")


@pytest.mark.parametrize(
    ("text", "issues"),
    [
        ("I am a real teacher, trust me.", ["claims_human"]),
        ("Tell me your home address so I can help.", ["asks_personal_data"]),
        ("Add me on Instagram.", ["arranges_contact"]),
        ("Let's factorise x^2 - 9 together. What two numbers multiply to -9?", []),
    ],
)
def test_output_checks(text: str, issues: list[str]) -> None:
    assert output_issues(text) == issues
