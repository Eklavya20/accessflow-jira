import hashlib
import sqlite3
import subprocess
import sys
import threading

import pytest

from accessflow.config import SafetyError
from accessflow.jira import JiraClient, JiraError, UncertainWrite
from accessflow.persistence import Store, issue_lock
from accessflow.processor import process

COMPLETE = (
    "Application: GitHub\nAccess level: Read-only\n"
    "Business justification: Review project documentation."
)


def test_worker_policy_recheck_can_block_after_refresh_before_post(workflow):
    client, api = workflow
    plan = process(client, "AFTEST-1")

    def reject_changed_scope(request, result):
        assert request.issue_id == result.issue_id
        raise SafetyError("Bounded worker policy changed; write blocked")

    with pytest.raises(SafetyError, match="policy changed"):
        process(
            client,
            "AFTEST-1",
            write=True,
            approved_sha256=plan.comment_sha256,
            before_post=reject_changed_scope,
        )
    assert api.posts == 0


def approved(client, *, retry=False):
    plan = process(client, "AFTEST-1")
    return process(client, "AFTEST-1", write=True, approved_sha256=plan.comment_sha256, retry=retry)


def test_dry_run_is_useful_and_durable_without_jira_writes(workflow, settings):
    client, api = workflow
    result = process(client, "AFTEST-1")
    assert result.decision.outcome == "ready_for_human_fulfillment"
    assert result.write_status == "planned"
    assert result.requester_available
    assert result.request_type == "Application access"
    assert "Ready for human fulfillment" in result.proposed_comment
    assert api.posts == 0
    with Store(settings.database_path()) as store:
        saved = store.latest(settings.jira_site_url, "AFTEST-1")
        assert saved["result_id"] == result.result_id
        assert (
            store.history(settings.jira_site_url, "AFTEST-1")[-1]["event"] == "request_classified"
        )


@pytest.mark.parametrize(
    "text,outcome",
    [
        (COMPLETE, "ready_for_human_fulfillment"),
        ("I need GitHub access.", "needs_information"),
        (
            "Application: Demo Analytics\nAccess level: Administrator\n"
            "Business justification: Migration",
            "privileged_review",
        ),
        ("Please give access to the reporting tool", "manual_triage"),
    ],
)
def test_all_outcomes_reach_proposed_internal_comment(workflow, text, outcome):
    client, api = workflow
    api.description = text
    result = process(client, "AFTEST-1")
    assert result.decision.outcome == outcome
    assert result.comment_sha256 == hashlib.sha256(result.proposed_comment.encode()).hexdigest()
    assert result.proposed_comment.startswith("AccessFlow automated triage (v1)")


def test_write_requires_exact_explicit_approval(workflow):
    client, api = workflow
    for approval in (None, "0" * 64):
        with pytest.raises(SafetyError, match="exact comment"):
            process(client, "AFTEST-1", write=True, approved_sha256=approval)
    assert api.posts == 0


def test_safe_internal_write_repeat_and_restart(workflow, settings):
    client, api = workflow
    first = approved(client)
    assert first.write_status == "created_and_verified"
    assert api.comments[0]["public"] is False
    assert api.posts == 1
    assert client.settings.accessflow_dry_run is True
    with JiraClient(settings, transport=client.http._transport) as fresh:
        repeated = approved(fresh)
    assert repeated.write_status == "already_verified"
    assert repeated.comment_id == first.comment_id
    assert api.posts == 1
    assert all(
        r.method == "GET" or (r.method == "POST" and r.url.path.endswith("/comment"))
        for r in api.calls
    )


def test_changed_request_creates_new_revision_and_stale_approval_is_blocked(workflow):
    client, api = workflow
    first = approved(client)
    api.description = COMPLETE.replace("Read-only", "Administrator")
    with pytest.raises(SafetyError, match="exact comment"):
        process(client, "AFTEST-1", write=True, approved_sha256=first.comment_sha256)
    updated = approved(client)
    assert updated.decision.outcome == "privileged_review"
    assert updated.revision == 2
    assert api.posts == 2
    assert approved(client).write_status == "already_verified"
    assert api.posts == 2


def test_reverting_to_previous_details_still_records_current_revision(workflow):
    client, api = workflow
    first = approved(client)
    api.description = COMPLETE.replace("Read-only", "Standard")
    approved(client)
    api.description = COMPLETE
    reverted = approved(client)
    assert reverted.revision == 3
    assert reverted.operation_key != first.operation_key
    assert api.posts == 3


def test_only_requester_public_formatted_comments_update_input(workflow):
    client, api = workflow
    api.description = "Application: GitHub"
    process(client, "AFTEST-1")
    api.comments.extend(
        [
            {
                "id": "101",
                "body": "Access level: Administrator",
                "public": True,
                "author": {"accountId": "other-user"},
            },
            {
                "id": "102",
                "body": "Access level: Administrator",
                "public": False,
                "author": {"accountId": "test-requester"},
            },
            {
                "id": "103",
                "body": "Access level: Read-only\nBusiness justification: Review docs",
                "public": True,
                "author": {"accountId": "test-requester"},
            },
        ]
    )
    updated = process(client, "AFTEST-1")
    assert updated.decision.access_level == "Read-only"
    assert updated.decision.outcome == "ready_for_human_fulfillment"
    assert updated.revision == 2


@pytest.mark.parametrize("failure", ["timeout", 429, 503])
def test_uncertain_post_reconciles_without_resend(workflow, failure):
    client, api = workflow
    api.post_failure = failure
    with pytest.raises(UncertainWrite):
        approved(client)
    assert api.posts == 1
    api.post_failure = None
    reconciled = approved(client, retry=True)
    assert reconciled.write_status == "reconciled"
    assert api.posts == 1


def test_crash_after_success_before_local_record_is_reconciled(workflow, settings, monkeypatch):
    client, api = workflow
    original = Store.state

    def crash(self, operation_key, state, **kwargs):
        if state == "pending" and kwargs.get("comment_id"):
            raise KeyboardInterrupt("Simulated process crash")
        return original(self, operation_key, state, **kwargs)

    monkeypatch.setattr(Store, "state", crash)
    with pytest.raises(KeyboardInterrupt):
        approved(client)
    assert api.posts == 1
    monkeypatch.setattr(Store, "state", original)
    with JiraClient(settings, transport=client.http._transport) as restarted:
        assert approved(restarted, retry=True).write_status == "reconciled"
    assert api.posts == 1


def test_uncertain_invisible_comment_never_blindly_reposts(workflow):
    client, api = workflow
    api.post_failure = "timeout"
    with pytest.raises(UncertainWrite):
        approved(client)
    api.comments.clear()  # A delayed remote write cannot be disproved by an empty read.
    api.post_failure = None
    with pytest.raises(SafetyError, match="remains uncertain"):
        approved(client, retry=True)
    assert api.posts == 1


@pytest.mark.parametrize("status", [401, 403])
def test_permission_denial_requires_explicit_retry(workflow, status):
    client, api = workflow
    api.deny_post = status
    with pytest.raises(JiraError):
        approved(client)
    api.deny_post = None
    with pytest.raises(SafetyError, match="use retry"):
        approved(client)
    assert approved(client, retry=True).write_status == "created_and_verified"
    assert api.posts == 2  # One definitive rejection and one successful authorized retry.
    assert len(api.comments) == 1


@pytest.mark.parametrize("statuses", [[429], [503, 503], [503, 503, 503]])
def test_read_failure_backoff_and_recovery(workflow, statuses):
    client, api = workflow
    api.read_failures = list(statuses)
    if len(statuses) == 3:
        with pytest.raises(JiraError):
            process(client, "AFTEST-1")
    result = process(client, "AFTEST-1")
    assert result.decision.outcome == "ready_for_human_fulfillment"
    assert api.posts == 0


def test_concurrent_processing_is_rejected_before_effect(workflow, settings):
    client, api = workflow
    errors = []
    with issue_lock(settings.database_path(), settings.jira_site_url, "9001"):

        def attempt():
            try:
                process(client, "AFTEST-1")
            except SafetyError as error:
                errors.append(str(error))

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert len(errors) == 1 and "already being processed" in errors[0]
    assert api.posts == 0
    assert process(client, "AFTEST-1").result_id > 0


def test_unauthorized_project_has_no_network_calls(workflow):
    client, api = workflow
    with pytest.raises(SafetyError):
        process(client, "BUSINESS-1")
    assert not api.calls


def test_privileged_request_never_approves_or_provisions(workflow):
    client, api = workflow
    api.description = COMPLETE.replace("Read-only", "Administrator")
    result = approved(client)
    assert result.decision.privileged
    assert result.decision.outcome == "privileged_review"
    assert not any("/approval" in r.url.path or "/transitions" in r.url.path for r in api.calls)
    assert {r.method for r in api.calls} <= {"GET", "POST"}
    assert all(r.url.path.endswith("/comment") for r in api.calls if r.method == "POST")


def test_persisted_history_contains_no_raw_requester_profile(workflow, settings):
    client, _ = workflow
    approved(client)
    with sqlite3.connect(settings.database_path()) as db:
        data = "".join(r[0] for r in db.execute("SELECT result_json FROM triage_results"))
    assert "private@example.invalid" not in data
    assert "test-requester" not in data


def test_status_change_without_business_change_does_not_duplicate(workflow):
    client, api = workflow
    original = approved(client)
    api.current_status = "In Progress"
    updated = approved(client)
    assert updated.current_status == "In Progress"
    assert updated.operation_key == original.operation_key
    assert api.posts == 1


def test_uncertain_older_revision_blocks_new_write(workflow):
    client, api = workflow
    api.post_failure = "timeout"
    with pytest.raises(UncertainWrite):
        approved(client)
    api.comments.clear()
    api.post_failure = None
    api.description = COMPLETE.replace("Read-only", "Administrator")
    with pytest.raises(SafetyError, match="earlier request revision"):
        approved(client, retry=True)
    assert api.posts == 1


def test_older_revision_can_be_reconciled_before_current_post(workflow):
    client, api = workflow
    api.post_failure = "timeout"
    with pytest.raises(UncertainWrite):
        approved(client)
    api.post_failure = None
    api.description = COMPLETE.replace("Read-only", "Administrator")
    assert approved(client, retry=True).write_status == "created_and_verified"
    assert api.posts == 2
    assert len(api.comments) == 2


def test_wrong_visibility_blocks_without_public_fallback_or_repost(workflow):
    client, api = workflow
    api.wrong_visibility = True
    with pytest.raises(SafetyError, match="internal visibility"):
        approved(client)
    with pytest.raises(SafetyError, match="internal visibility"):
        approved(client, retry=True)
    assert api.posts == 1


def test_denied_effective_permissions_have_no_post(workflow):
    client, api = workflow
    api.permissions = False
    with pytest.raises(SafetyError, match="Add Comments"):
        approved(client)
    assert api.posts == 0


def test_missing_requester_identity_does_not_trust_public_updates(workflow):
    client, api = workflow
    api.reporter = None
    api.description = "Application: GitHub"
    api.comments.append(
        {
            "id": "101",
            "body": "Access level: Standard\nBusiness justification: Work",
            "public": True,
            "author": {"accountId": "unverified-user"},
        }
    )
    result = process(client, "AFTEST-1")
    assert not result.requester_available
    assert result.decision.outcome == "needs_information"


def test_operating_system_lock_blocks_another_process_and_recovers_after_exit(settings):
    code = (
        "import sys; from pathlib import Path; from accessflow.persistence import issue_lock; "
        "from accessflow.config import SafetyError\n"
        "try:\n"
        " with issue_lock(Path(sys.argv[1]), 'sandbox', '9001'): pass\n"
        "except SafetyError: sys.exit(7)\n"
    )
    command = [sys.executable, "-c", code, str(settings.database_path())]
    with issue_lock(settings.database_path(), "sandbox", "9001"):
        assert subprocess.run(command, capture_output=True, check=False).returncode == 7
    assert subprocess.run(command, capture_output=True, check=False).returncode == 0
