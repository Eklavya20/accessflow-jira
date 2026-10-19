import hashlib
import json
import threading

import httpx
import pytest

from accessflow.config import SafetyError
from accessflow.jira import JiraClient, JiraError
from accessflow.persistence import Store
from accessflow.worker import Worker, discover_requests, retry_job
from accessflow.worker_store import WorkerStore


@pytest.fixture
def polling(workflow, settings):
    underlying, api = workflow
    settings.accessflow_request_type_ids = "12"
    api.updated = "2026-10-19T12:00:00Z"
    api.list_failure = None
    api.issue_failure = None
    base = underlying.http._transport

    def handler(request):
        if request.url.path == "/rest/servicedeskapi/request":
            api.calls.append(request)
            if api.list_failure:
                return httpx.Response(api.list_failure, json={}, headers={"Retry-After": "600"})
            return httpx.Response(
                200,
                json=api.page(
                    [
                        {
                            "issueId": "9001",
                            "issueKey": "AFTEST-1",
                            "serviceDeskId": "7",
                            "requestTypeId": "12",
                        }
                    ]
                ),
            )
        if request.url.path == "/rest/api/3/issue/AFTEST-1":
            if api.issue_failure:
                return httpx.Response(api.issue_failure, json={})
            response = base.handle_request(request)
            data = response.json()
            data["fields"]["updated"] = api.updated
            return httpx.Response(response.status_code, json=data)
        return base.handle_request(request)

    def factory(config):
        return JiraClient(config, transport=httpx.MockTransport(handler), sleep=lambda _: None)

    with factory(settings) as client:
        yield client, api, factory


def get_job(settings):
    with WorkerStore(settings.database_path()) as store:
        return store.job(settings.jira_site_url, "9001")


def test_discovers_new_request_and_persists_audit(polling, settings):
    client, api, _ = polling
    Worker(settings).poll(client)
    job = get_job(settings)
    assert job["state"] == "done"
    assert job["outcome"] == "ready_for_human_fulfillment"
    assert job["source_hash"] and job["processed_at"]
    with Store(settings.database_path()) as store:
        assert (
            store.history(settings.jira_site_url, "AFTEST-1")[-1]["event"]
            == "worker_request_completed"
        )
    assert api.posts == 0


def test_unchanged_poll_and_restart_skip_processing(polling, settings):
    client, api, _ = polling
    Worker(settings, clock=lambda: 1000).poll(client)
    calls = len(api.calls)
    Worker(settings, clock=lambda: 1060).poll(client)
    assert len(api.calls) - calls == 2  # Collection + cheap updated/project read.
    with WorkerStore(settings.database_path()) as store:
        assert store.db.execute("SELECT count(*) FROM triage_results").fetchone()[0] == 1
        assert store.runtime(settings.jira_site_url)["last_poll_summary"]["skipped"] == 1


def test_updated_description_reevaluates(polling, settings):
    client, api, _ = polling
    worker = Worker(settings)
    worker.poll(client)
    api.description = "Application: GitHub"
    api.updated = "2026-10-19T13:00:00Z"
    worker.poll(client)
    assert get_job(settings)["outcome"] == "needs_information"
    with Store(settings.database_path()) as store:
        assert store.latest(settings.jira_site_url, "AFTEST-1")["revision"] == 2


def test_self_comments_and_status_changes_do_not_loop(polling, settings):
    client, api, _ = polling
    worker = Worker(settings)
    worker.poll(client)
    api.comments.append(
        {
            "id": "300",
            "public": False,
            "body": "AccessFlow automated triage (v1)\nApplication: Confluence",
            "author": {"accountId": api.reporter},
        }
    )
    api.current_status = "In progress"
    api.updated = "2026-10-19T13:00:00Z"
    worker.poll(client)
    with WorkerStore(settings.database_path()) as store:
        assert store.db.execute("SELECT count(*) FROM triage_results").fetchone()[0] == 1
    assert api.posts == 0


def test_periodic_rescan_detects_requester_correction_without_updated_change(polling, settings):
    client, api, _ = polling
    api.description = "Application: GitHub"
    Worker(settings, clock=lambda: 1000).poll(client)
    api.comments.append(
        {
            "id": "301",
            "public": True,
            "author": {"accountId": api.reporter},
            "body": "Access level: Standard\nBusiness justification: Project support",
        }
    )
    Worker(settings, clock=lambda: 1301).poll(client)
    assert get_job(settings)["outcome"] == "ready_for_human_fulfillment"


def test_crashed_running_job_recovers(polling, settings):
    client, api, _ = polling
    Worker(settings).poll(client)
    with WorkerStore(settings.database_path()) as store:
        store.update_job(settings.jira_site_url, "9001", state="running")
    Worker(settings).poll(client)
    assert get_job(settings)["state"] == "done"
    assert api.posts == 0


def test_partial_failure_persists_and_retry_is_scheduled(polling, settings):
    client, api, _ = polling
    api.issue_failure = 503
    worker = Worker(settings, clock=lambda: 1000)
    worker.poll(client)
    job = get_job(settings)
    assert job["state"] == "retry" and job["retry_at"] == 1060 and job["attempts"] == 1
    api.issue_failure = None
    worker.poll(client)
    assert get_job(settings)["state"] == "retry"
    Worker(settings, clock=lambda: 1060).poll(client)
    assert get_job(settings)["state"] == "done"


def test_authentication_failure_terminal_and_safe_manual_retry(polling, settings):
    client, api, _ = polling
    api.issue_failure = 401
    with pytest.raises(JiraError):
        Worker(settings).poll(client)
    assert get_job(settings)["state"] == "failed"
    assert retry_job(settings, "AFTEST-1")["state"] == "retry"
    api.issue_failure = None
    Worker(settings).poll(client)
    assert get_job(settings)["state"] == "done"
    with pytest.raises(SafetyError):
        retry_job(settings, "AFTEST-1")
    assert api.posts == 0


def test_retry_attempts_are_bounded(polling, settings):
    client, api, _ = polling
    settings.accessflow_retry_attempts = 2
    api.issue_failure = 503
    Worker(settings, clock=lambda: 1000).poll(client)
    Worker(settings, clock=lambda: 1060).poll(client)
    assert get_job(settings)["state"] == "failed"
    assert get_job(settings)["attempts"] == 2


def test_rate_limit_preserves_retry_after(polling, settings):
    client, api, _ = polling
    api.list_failure = 429
    with pytest.raises(JiraError) as caught:
        Worker(settings).poll(client)
    assert caught.value.retry_after == 600
    assert api.posts == 0


def test_paginated_discovery_deduplicates_and_scopes(settings):
    settings.accessflow_request_type_ids = "12"
    starts = []

    def handler(request):
        start = int(request.url.params["start"])
        starts.append(start)
        assert request.url.params["requestTypeId"] == "12"
        assert request.url.params["serviceDeskId"] == "7"
        return httpx.Response(
            200,
            json={
                "values": [
                    {
                        "issueId": "9001",
                        "issueKey": "AFTEST-1",
                        "serviceDeskId": "7",
                        "requestTypeId": "12",
                    }
                ],
                "isLastPage": start == 1,
            },
        )

    with JiraClient(settings, transport=httpx.MockTransport(handler)) as client:
        assert discover_requests(client) == {"9001": "AFTEST-1"}
    assert starts == [0, 1]


@pytest.mark.parametrize(
    "change",
    [
        {"issueKey": "OTHER-1"},
        {"serviceDeskId": "8"},
        {"requestTypeId": "13"},
        {"issueId": "invalid"},
    ],
)
def test_discovery_rejects_out_of_scope_responses(settings, change):
    settings.accessflow_request_type_ids = "12"
    row = {"issueId": "9001", "issueKey": "AFTEST-1", "serviceDeskId": "7", "requestTypeId": "12"}
    row.update(change)
    with JiraClient(
        settings,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"values": [row], "isLastPage": True})
        ),
    ) as client:
        with pytest.raises(SafetyError):
            discover_requests(client)


def test_worker_concurrency_lock_and_shutdown(polling, settings):
    _, _, factory = polling
    worker = Worker(settings, client_factory=factory)
    polled = threading.Event()
    original = worker.poll

    def poll(client):
        original(client)
        polled.set()

    worker.poll = poll
    thread = threading.Thread(target=worker.run)
    thread.start()
    assert polled.wait(5)
    with pytest.raises(SafetyError, match="already being processed"):
        Worker(settings, client_factory=factory).run()
    worker.stop.set()
    thread.join(5)
    assert not thread.is_alive()
    with WorkerStore(settings.database_path()) as store:
        assert store.runtime(settings.jira_site_url)["state"] == "stopped"
        assert store.runtime(settings.jira_site_url)["next_poll_at"] > 0


def test_global_write_flag_cannot_reuse_old_comment_approval(polling, settings):
    client, api, _ = polling
    settings.accessflow_worker_write_enabled = True
    Worker(settings).poll(client)
    assert get_job(settings)["state"] == "failed"
    assert api.posts == 0


def test_budget_is_durable_and_one_action_per_issue(settings):
    with WorkerStore(settings.database_path()) as store:
        store.reserve_write("policy", "op1", "9001", 1)
    with WorkerStore(settings.database_path()) as store:
        store.reserve_write("policy", "op1", "9001", 1)
        with pytest.raises(SafetyError, match="one revision"):
            store.reserve_write("policy", "op2", "9001", 1)
        with pytest.raises(SafetyError, match="exhausted"):
            store.reserve_write("policy", "op3", "9002", 1)


def test_worker_schema_preserves_old_journals(settings):
    with WorkerStore(settings.database_path()) as store:
        store.audit(settings.jira_site_url, "AFTEST-1", "preserved")
    with Store(settings.database_path()) as store:
        assert store.history(settings.jira_site_url, "AFTEST-1")[0]["event"] == "preserved"


def test_no_raw_request_body_in_worker_job_error(polling, settings):
    client, api, _ = polling
    api.issue_failure = 403
    with pytest.raises(JiraError):
        Worker(settings).poll(client)
    assert "private" not in json.dumps(get_job(settings)).lower()


def allow_one_test_comment(settings, tmp_path):
    settings.accessflow_worker_write_enabled = True
    settings.accessflow_dry_run = False
    settings.accessflow_write_policy_path = tmp_path / "authorized.json"
    doc = {
        "version": "test-only",
        "approved": True,
        "site": settings.jira_site_url,
        "project": "AFTEST",
        "service_desk_id": "7",
        "request_type_ids": ["12"],
        "issue_keys": ["AFTEST-1"],
        "summary_prefix": "Access request",
        "expires_at": "2099-01-01T00:00:00Z",
        "max_actions": 1,
        "allowed_outcomes": ["ready_for_human_fulfillment"],
    }
    raw = json.dumps(doc).encode()
    settings.accessflow_write_policy_path.write_bytes(raw)
    settings.accessflow_approved_policy_sha256 = hashlib.sha256(raw).hexdigest()


def test_explicit_bounded_worker_write_and_restart_do_not_duplicate(polling, settings, tmp_path):
    client, api, _ = polling
    allow_one_test_comment(settings, tmp_path)
    Worker(settings, clock=lambda: 1000).poll(client)
    assert get_job(settings)["comment_id"] == "1"
    assert api.posts == 1 and api.comments[0]["public"] is False
    with WorkerStore(settings.database_path()) as store:
        before = [
            e
            for e in store.history(settings.jira_site_url, "AFTEST-1")
            if e["event"] == "worker_before_comment"
        ]
        assert len(before) == 1 and before[0]["details"]["status_id"] == "10"
    api.updated = "2026-10-19T15:00:00Z"
    Worker(settings, clock=lambda: 1400).poll(client)
    assert api.posts == 1
    with WorkerStore(settings.database_path()) as store:
        store.update_job(settings.jira_site_url, "9001", state="running")
    Worker(settings, clock=lambda: 1500).poll(client)
    assert api.posts == 1 and get_job(settings)["state"] == "done"


def test_uncertain_automatic_write_reconciles_after_restart(polling, settings, tmp_path):
    # This exercises the same authorization setup, with a remote success/local timeout.
    client, api, _ = polling
    api.post_failure = "timeout"
    allow_one_test_comment(settings, tmp_path)
    Worker(settings, clock=lambda: 1000).poll(client)
    assert get_job(settings)["state"] == "retry" and api.posts == 1
    api.post_failure = None
    Worker(settings, clock=lambda: 1060).poll(client)
    assert get_job(settings)["state"] == "done" and get_job(settings)["comment_id"] == "1"
    assert api.posts == 1


def test_worker_schema_upgrade_preserves_jobs(settings):
    with WorkerStore(settings.database_path()) as store:
        store.discover(settings.jira_site_url, "9001", "AFTEST-1")
        with store.db:
            store.db.execute("ALTER TABLE worker_jobs DROP COLUMN jira_updated_at")
            store.db.execute("UPDATE worker_schema SET version=1")
    with WorkerStore(settings.database_path()) as store:
        assert store.job(settings.jira_site_url, "9001")["issue_key"] == "AFTEST-1"
        assert store.db.execute("SELECT version FROM worker_schema").fetchone()[0] == 2


class StopAfterWait:
    def __init__(self):
        self.stopped = False

    def is_set(self):
        return self.stopped

    def wait(self, timeout=None):
        self.stopped = True


def test_poll_interval_schedules_no_early_second_scan(polling, settings):
    _, _, factory = polling
    Worker(settings, client_factory=factory, clock=lambda: 1000, stop=StopAfterWait()).run()
    with WorkerStore(settings.database_path()) as store:
        runtime = store.runtime(settings.jira_site_url)
        assert runtime["next_poll_at"] == 1060
        assert runtime["last_poll_summary"]["processed"] == 1


def test_global_rate_limit_deadline_and_failure_count_survive_restart(polling, settings):
    _, api, factory = polling
    api.list_failure = 429
    Worker(settings, client_factory=factory, clock=lambda: 1000, stop=StopAfterWait()).run()
    with WorkerStore(settings.database_path()) as store:
        assert store.runtime(settings.jira_site_url)["next_poll_at"] == 1600
        assert store.runtime(settings.jira_site_url)["consecutive_poll_failures"] == 1
    calls = len(api.calls)
    Worker(settings, client_factory=factory, clock=lambda: 1100, stop=StopAfterWait()).run()
    assert len(api.calls) == calls
    with WorkerStore(settings.database_path()) as store:
        assert store.runtime(settings.jira_site_url)["consecutive_poll_failures"] == 1


def test_write_approval_change_revisits_previous_dry_run(polling, settings, tmp_path):
    client, api, _ = polling
    Worker(settings, clock=lambda: 1000).poll(client)
    assert api.posts == 0
    allow_one_test_comment(settings, tmp_path)
    Worker(settings, clock=lambda: 1001).poll(client)
    assert api.posts == 1


def test_activating_policy_does_not_reprocess_unapproved_tickets(polling, settings, tmp_path):
    client, api, _ = polling
    Worker(settings, clock=lambda: 1000).poll(client)
    allow_one_test_comment(settings, tmp_path)
    doc = json.loads(settings.accessflow_write_policy_path.read_text())
    doc["issue_keys"] = ["AFTEST-2"]
    raw = json.dumps(doc).encode()
    settings.accessflow_write_policy_path.write_bytes(raw)
    settings.accessflow_approved_policy_sha256 = hashlib.sha256(raw).hexdigest()
    Worker(settings, clock=lambda: 1001).poll(client)
    with WorkerStore(settings.database_path()) as store:
        assert store.db.execute("SELECT count(*) FROM triage_results").fetchone()[0] == 1
    assert api.posts == 0 and get_job(settings)["state"] == "done"
