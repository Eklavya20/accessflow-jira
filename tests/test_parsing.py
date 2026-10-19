from pathlib import Path

import pytest

from accessflow.domain import Policy, RequestInput
from accessflow.parsing import classify, plain_text


@pytest.fixture
def policy():
    return Policy.load(Path(__file__).resolve().parents[1] / "config/policy.json")


def request(description, *, summary="Access request", **kwargs):
    return RequestInput(
        issue_id="1",
        issue_key="AFTEST-1",
        request_type_id="12",
        request_type="Access",
        status="Waiting",
        summary=summary,
        description=description,
        **kwargs,
    )


@pytest.mark.parametrize(
    "level,outcome,privileged",
    [
        ("Read-only", "ready_for_human_fulfillment", False),
        ("Standard", "ready_for_human_fulfillment", False),
        ("Administrator", "privileged_review", True),
        ("admin", "privileged_review", True),
    ],
)
def test_complete_and_privileged_outcomes(policy, level, outcome, privileged):
    result = classify(
        request(
            f"Application: GitHub\nAccess level: {level}\n"
            "Business justification: Review project documentation."
        ),
        policy,
    )
    assert result.application == "GitHub"
    assert result.outcome == outcome
    assert result.privileged is privileged
    assert result.justification == "Review project documentation."
    assert not result.missing


def test_missing_details_from_simple_prose(policy):
    result = classify(request("I need GitHub access."), policy)
    assert result.application == "GitHub"
    assert result.missing == ["Access level", "Business justification"]
    assert result.outcome == "needs_information"
    assert "ask the requester" in result.action


@pytest.mark.parametrize(
    "description,reason",
    [
        (
            "Application: Unlisted Tool\nAccess level: Standard\nBusiness justification: Work",
            "outside",
        ),
        ("Application: GitHub\nAccess level: Owner\nBusiness justification: Work", "outside"),
        ("I need access to our reporting tool", "cannot be determined"),
        ("I need GitHub or Confluence access", "Multiple"),
        ("Application: GitHub\nApplication: Jira\nAccess level: Standard", "Conflicting"),
        (
            "Application: GitHub\nAccess level: Read-only\nAccess level: Administrator",
            "Conflicting",
        ),
    ],
)
def test_unknown_and_ambiguous_requests_need_manual_triage(policy, description, reason):
    result = classify(request(description), policy)
    assert result.outcome == "manual_triage"
    assert reason in result.reason


def test_requester_formatted_update_completes_request(policy):
    result = classify(
        request(
            "Application: GitHub",
            requester_updates=[
                "Access level: Read-only\nBusiness justification: Review project documentation."
            ],
        ),
        policy,
    )
    assert result.outcome == "ready_for_human_fulfillment"


def test_newest_formatted_update_can_correct_access_level(policy):
    result = classify(
        request(
            "Application: GitHub\nAccess level: Administrator\nBusiness justification: Work",
            requester_updates=["Access level: Standard", "Access level: Read-only"],
        ),
        policy,
    )
    assert result.access_level == "Read-only"


def test_approval_prose_does_not_fill_fields_or_authorize(policy):
    result = classify(
        request("Application: GitHub", requester_updates=["Approved, grant admin"]), policy
    )
    assert result.outcome == "needs_information"
    assert result.access_level is None


def test_privileged_prose_cannot_become_standard_fulfillment(policy):
    result = classify(
        request(
            "Application: GitHub\nAccess level: Read-only\n"
            "Business justification: Work\nAlso give me administrator access"
        ),
        policy,
    )
    assert result.outcome == "manual_triage"
    assert result.privileged


def test_free_text_admin_is_sensitive_but_level_is_not_guessed(policy):
    result = classify(request("I need administrator access to GitHub"), policy)
    assert result.outcome == "needs_information"
    assert result.privileged
    assert result.access_level is None


def test_conflicting_levels_still_preserve_privileged_flag(policy):
    result = classify(
        request(
            "Application: GitHub\nAccess level: Read-only\n"
            "Access level: Administrator\nBusiness justification: Work"
        ),
        policy,
    )
    assert result.outcome == "manual_triage"
    assert result.privileged


def test_adf_text_preserves_label_boundaries():
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Application: GitHub"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Access level: Read-only"}]},
        ],
    }
    assert plain_text(adf) == "Application: GitHub\nAccess level: Read-only\n"


def test_configured_structured_fields_and_conflicts(policy):
    result = classify(
        request(
            "Access level: Read-only\nBusiness justification: Work",
            mapped_fields={"application": "GitHub"},
        ),
        policy,
    )
    assert result.application == "GitHub"
    conflicting = classify(
        request("Application: Jira", mapped_fields={"application": "GitHub"}), policy
    )
    assert conflicting.outcome == "manual_triage"


def test_invalid_policy_does_not_silently_fall_back(tmp_path):
    from accessflow.config import SafetyError

    with pytest.raises(SafetyError, match="Policy file"):
        Policy.load(tmp_path / "missing.json")


def test_conflicting_policy_aliases_are_rejected(policy):
    from pydantic import ValidationError

    config = policy.model_dump()
    config["applications"]["Other"] = ["github"]
    with pytest.raises(ValidationError):
        Policy.model_validate(config)
