import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from accessflow.config import SafetyError
from accessflow.worker_policy import authorize
from accessflow.worker_store import WorkerStore


@pytest.fixture
def authority(settings, tmp_path):
    settings.accessflow_worker_write_enabled = True
    settings.accessflow_dry_run = False
    settings.accessflow_request_type_ids = "12"
    settings.accessflow_write_policy_path = tmp_path / "write-policy.json"
    doc = {
        "version": "test-v1",
        "approved": True,
        "site": settings.jira_site_url,
        "project": "AFTEST",
        "service_desk_id": "7",
        "request_type_ids": ["12"],
        "issue_keys": ["AFTEST-1"],
        "summary_prefix": "TEST - AccessFlow M3",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "max_actions": 1,
        "public": False,
        "operation": "internal_triage_comment",
        "allowed_outcomes": ["ready_for_human_fulfillment"],
    }

    def save(document):
        raw = json.dumps(document).encode()
        settings.accessflow_write_policy_path.write_bytes(raw)
        settings.accessflow_approved_policy_sha256 = hashlib.sha256(raw).hexdigest()

    save(doc)
    result = SimpleNamespace(
        operation_key="operation",
        issue_id="9001",
        request_type_id="12",
        decision=SimpleNamespace(outcome="ready_for_human_fulfillment"),
    )
    request = SimpleNamespace(
        issue_id="9001",
        issue_key="AFTEST-1",
        request_type_id="12",
        summary="TEST - AccessFlow M3 automatic write",
    )
    return doc, save, result, request


def test_exact_approved_bounded_policy_reserves_durably(settings, authority):
    _, _, result, request = authority
    with WorkerStore(settings.database_path()) as store:
        fingerprint = authorize(settings, store, result, request)
    with WorkerStore(settings.database_path()) as store:
        assert authorize(settings, store, result, request) == fingerprint
        assert store.db.execute("SELECT count(*) FROM worker_write_budget").fetchone()[0] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"approved": False},
        {"public": True},
        {"project": "OTHER"},
        {"service_desk_id": "8"},
        {"site": "https://other.atlassian.net"},
        {"issue_keys": ["AFTEST-2"]},
        {"request_type_ids": ["13"]},
        {"summary_prefix": "ANOTHER TEST"},
        {"expires_at": "2020-01-01T00:00:00Z"},
        {"operation": "approve"},
        {"allowed_outcomes": ["privileged_review"]},
    ],
)
def test_wrong_or_unapproved_scope_never_reserves(settings, authority, changes):
    doc, save, result, request = authority
    save({**doc, **changes})
    with WorkerStore(settings.database_path()) as store:
        with pytest.raises(SafetyError):
            authorize(settings, store, result, request)
        assert store.db.execute("SELECT count(*) FROM worker_write_budget").fetchone()[0] == 0


@pytest.mark.parametrize(
    "gate",
    ["accessflow_worker_write_enabled", "accessflow_dry_run", "accessflow_approved_policy_sha256"],
)
def test_independent_write_gates(settings, authority, gate):
    _, _, result, request = authority
    setattr(
        settings,
        gate,
        {
            "accessflow_worker_write_enabled": False,
            "accessflow_dry_run": True,
            "accessflow_approved_policy_sha256": "unapproved",
        }[gate],
    )
    with WorkerStore(settings.database_path()) as store:
        with pytest.raises(SafetyError):
            authorize(settings, store, result, request)


def test_modified_policy_hash_invalidates_authority(settings, authority):
    _, _, result, request = authority
    with settings.accessflow_write_policy_path.open("a") as file:
        file.write("\n")
    with WorkerStore(settings.database_path()) as store:
        with pytest.raises(SafetyError):
            authorize(settings, store, result, request)
