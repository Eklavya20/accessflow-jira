import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from accessflow.config import SafetyError
from accessflow.jira import UncertainWrite
from accessflow.probe import ProbeJournal, probe_comment


def probe(client, public=False):
    return probe_comment(client, confirmed_key="AFTEST-1", public=public)


def test_probe_dry_run_has_no_remote_or_database_writes(client, settings, sandbox):
    assert probe(client)["mode"] == "dry_run"
    assert sandbox.posts == 0
    assert not settings.database_path().exists()


def test_explicit_confirmation_required(client, sandbox):
    with pytest.raises(SafetyError, match="Explicit confirmation"):
        probe_comment(client, confirmed_key="OTHER-1", public=False)
    assert not sandbox.calls


@pytest.mark.parametrize("public", [True, False])
def test_write_read_back_and_restart_duplicate_prevention(client, settings, sandbox, public):
    settings.accessflow_dry_run = False
    first = probe(client, public)
    assert first["write"] == "created_and_verified"
    assert sandbox.comments[0]["public"] is public
    # Each call opens/closes the journal; a fresh client recreates a process restart.
    from accessflow.jira import JiraClient

    with JiraClient(settings, transport=client.http._transport) as restarted:
        second = probe(restarted, public)
    assert second["write"] == "already_verified"
    assert first["comment_id"] == second["comment_id"]
    assert sandbox.posts == 1
    with sqlite3.connect(settings.database_path()) as db:
        assert db.execute("SELECT state FROM connectivity_probes").fetchone() == ("verified",)


@pytest.mark.parametrize("failure", ["timeout", 429, 500, 503])
def test_uncertain_post_is_reconciled_without_resend(client, settings, sandbox, failure):
    settings.accessflow_dry_run = False
    sandbox.post_failure = failure
    with pytest.raises(UncertainWrite):
        probe(client)
    assert sandbox.posts == 1
    sandbox.post_failure = None
    assert probe(client)["write"] == "reconciled"
    assert sandbox.posts == 1


def test_pending_without_visible_comment_blocks_resend(client, settings, sandbox):
    settings.accessflow_dry_run = False
    operation = hashlib.sha256(b"https://sandbox.atlassian.net|9001|probe-v1").hexdigest()
    with ProbeJournal(settings.database_path()) as journal:
        journal.reserve(operation, False)
    with pytest.raises(SafetyError, match="No POST was retried"):
        probe(client)
    assert sandbox.posts == 0


def test_atomic_reservation_across_concurrent_connections(settings):
    path = settings.database_path()
    with ProbeJournal(path):
        pass

    def reserve(_):
        with ProbeJournal(path) as journal:
            return journal.reserve("same-operation", False)[1]

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(reserve, range(2))) == [False, True]


def test_wrong_visibility_fails_readback(client, settings, sandbox):
    settings.accessflow_dry_run = False
    sandbox.wrong_visibility = True
    with pytest.raises(SafetyError, match="read-back verification"):
        probe(client)
    assert sandbox.posts == 1
    with pytest.raises(SafetyError, match="read-back verification"):
        probe(client)
    assert sandbox.posts == 1


def test_no_public_fallback_or_unauthorized_post(client, settings, sandbox):
    settings.accessflow_dry_run = False
    sandbox.permissions = False
    with pytest.raises(SafetyError, match="Add Comments"):
        probe(client)
    assert sandbox.posts == 0


def test_changed_visibility_does_not_create_second_probe(client, settings, sandbox):
    settings.accessflow_dry_run = False
    probe(client, False)
    with pytest.raises(SafetyError, match="different visibility"):
        probe(client, True)
    assert sandbox.posts == 1


@pytest.mark.parametrize("status", [401, 403])
def test_post_denial_stops_without_public_fallback(client, settings, sandbox, status):
    from accessflow.jira import JiraError

    settings.accessflow_dry_run = False
    sandbox.post_failure = status
    with pytest.raises(JiraError, match=f"HTTP {status}"):
        probe(client)
    assert sandbox.posts == 1
    assert sandbox.comments[0]["public"] is False


def test_post_guard_revalidates_target(client, settings, sandbox):
    settings.accessflow_dry_run = False
    sandbox.project_key = "BUSINESS"
    with pytest.raises(SafetyError, match="Actual Jira issue project"):
        client.post_probe_comment("9001", "body", False)
    assert sandbox.posts == 0


def test_same_project_other_issue_cannot_receive_probe(client, settings, sandbox):
    settings.accessflow_dry_run = False
    with pytest.raises(SafetyError, match="outside the designated sandbox issue"):
        client.post_probe_comment("9002", "body", False)
    assert sandbox.posts == 0


def test_configured_comment_is_posted_exactly_without_marker(client, settings, sandbox):
    settings.accessflow_dry_run = False
    settings.accessflow_probe_comment_body = "Operator-approved exact text."
    first = probe(client)
    assert first["body"] == "Operator-approved exact text."
    assert sandbox.comments[0]["body"] == first["body"]
    assert probe(client)["write"] == "already_verified"
    assert sandbox.posts == 1


def test_different_comment_text_cannot_create_second_probe(client, settings, sandbox):
    settings.accessflow_dry_run = False
    probe(client)
    settings.accessflow_probe_comment_body = "Changed text"
    with pytest.raises(SafetyError, match="different text"):
        probe(client)
    assert sandbox.posts == 1


def test_legacy_journal_upgrade_preserves_verified_comment(client, settings, sandbox):
    settings.accessflow_dry_run = False
    probe(client)
    with sqlite3.connect(settings.database_path()) as db:
        db.execute("ALTER TABLE connectivity_probes DROP COLUMN body_sha256")
    assert probe(client)["write"] == "already_verified"
    assert sandbox.posts == 1
