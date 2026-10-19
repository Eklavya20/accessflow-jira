import json

import pytest

from accessflow.config import SafetyError
from accessflow.discovery import discover


def test_discovery_and_required_fields(client):
    report = discover(client, check_target=True)
    assert report["authentication"] == "verified"
    assert report["request_types"][0]["fields"][0]["required"] is True
    assert report["target"]["issue_id"] == "9001"
    assert report["target"]["permissions"]["ADD_COMMENTS"] is True
    assert report["capabilities"]["transitions"]["observed"][0]["id"] == "21"
    assert report["write"] == "not_attempted"
    assert report["milestone_1"] == "incomplete"
    assert "Private content" not in json.dumps(report)
    assert "private@example.invalid" not in json.dumps(report)
    assert "Empty results do not prove" in report["capabilities"]["approvals"]["note"]


def test_initial_inventory_needs_no_target(client, settings, sandbox):
    settings.jira_project_key = ""
    settings.jira_allowed_project_keys = ""
    settings.jira_test_issue_key = ""
    report = discover(client)
    assert report["projects"]
    assert not report["request_types"]
    assert not any("/issue/" in r.url.path for r in sandbox.calls)


def test_optional_capability_failure_is_explicit(client, sandbox):
    sandbox.approval_status = 403
    report = discover(client, check_target=True)
    assert report["capabilities"]["approvals"]["read"] == "unverified"
    assert report["capabilities"]["approvals"]["http_status"] == 403


def test_actual_project_is_verified(client, sandbox):
    sandbox.project_key = "BUSINESS"
    with pytest.raises(SafetyError, match="Actual Jira issue project"):
        client.target()


def test_approval_read_can_be_disabled_without_hitting_missing_scope(client, settings, sandbox):
    settings.jira_query_approvals = False
    report = discover(client, check_target=True)
    assert report["capabilities"]["approvals"]["read"] == "not_checked"
    assert not any(request.url.path.endswith("/approval") for request in sandbox.calls)
