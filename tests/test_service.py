import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from accessflow.config import SafetyError
from accessflow.service import create_app
from accessflow.worker_store import WorkerStore


class WaitingWorker:
    def __init__(self, settings):
        self.settings = settings
        self.stop = threading.Event()
        self.run_id = "test-worker"

    def run(self):
        self.stop.wait()


@pytest.fixture
def service(settings):
    settings.accessflow_request_type_ids = "12"
    settings.accessflow_admin_token = SecretStr("a" * 40)
    app = create_app(settings, worker_factory=WaitingWorker)
    with TestClient(app) as client:
        yield client, app


def test_admin_requires_authentication(service):
    client, _ = service
    for path in ["/admin/status", "/admin/issues/AFTEST-1", "/admin/issues/AFTEST-1/audit"]:
        assert client.get(path).status_code == 401
    for path in ["/admin/issues/AFTEST-1/retry", "/admin/shutdown"]:
        assert client.post(path).status_code == 401
    assert client.get("/admin/status", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_authenticated_status_and_safe_retry(service, settings):
    client, _ = service
    auth = {"Authorization": "Bearer " + "a" * 40}
    with WorkerStore(settings.database_path()) as store:
        store.discover(settings.jira_site_url, "9001", "AFTEST-1")
        store.update_job(
            settings.jira_site_url, "9001", state="failed", error="Jira returned HTTP 401"
        )
    result = client.get("/admin/status", headers=auth)
    assert result.status_code == 200 and result.json()["jobs"][0]["state"] == "failed"
    assert "token" not in result.text
    assert client.post("/admin/issues/OTHER-1/retry", headers=auth).status_code == 409
    assert client.post("/admin/issues/AFTEST-1/retry", headers=auth).status_code == 200


def test_health_checks_actual_worker_freshness(service, settings):
    client, _ = service
    assert client.get("/health").status_code == 503
    with WorkerStore(settings.database_path()) as store:
        store.save_runtime(
            settings.jira_site_url,
            {
                "state": "waiting",
                "heartbeat": time.time(),
                "run_id": "test-worker",
                "started_at": (datetime.now(UTC) - timedelta(seconds=10)).isoformat(),
                "last_successful_poll": datetime.now(UTC).isoformat(),
                "next_poll_at": time.time() + 60,
            },
        )
    assert client.get("/health").status_code == 200
    with WorkerStore(settings.database_path()) as store:
        data = store.runtime(settings.jira_site_url)
        data["heartbeat"] -= 100
        store.save_runtime(settings.jira_site_url, data)
    assert client.get("/health").status_code == 503


@pytest.mark.parametrize("state", ["polling", "waiting"])
def test_health_rejects_success_inherited_from_previous_run(service, settings, state):
    client, _ = service
    current = datetime.now(UTC)
    with WorkerStore(settings.database_path()) as store:
        store.save_runtime(
            settings.jira_site_url,
            {
                "state": state,
                "run_id": "test-worker",
                "heartbeat": time.time(),
                "started_at": current.isoformat(),
                "last_successful_poll": (current - timedelta(minutes=1)).isoformat(),
                "next_poll_at": time.time() + 60,
            },
        )
    assert client.get("/health").status_code == 503


@pytest.mark.parametrize(
    "timestamps",
    [
        {},
        {"started_at": "invalid", "last_successful_poll": "invalid"},
        {"started_at": "2026-10-19T00:00:00", "last_successful_poll": "2026-10-19T00:00:01"},
    ],
)
def test_health_rejects_missing_or_invalid_poll_times(service, settings, timestamps):
    client, _ = service
    with WorkerStore(settings.database_path()) as store:
        store.save_runtime(
            settings.jira_site_url,
            {
                "state": "waiting",
                "run_id": "test-worker",
                "heartbeat": time.time(),
                "next_poll_at": time.time() + 60,
                **timestamps,
            },
        )
    assert client.get("/health").status_code == 503


def test_health_mode_respects_global_dry_run(service, settings):
    client, _ = service
    settings.accessflow_worker_write_enabled = True
    settings.accessflow_dry_run = True
    assert client.get("/health").json()["mode"] == "dry_run"


def test_shutdown_is_graceful_and_authenticated(service):
    client, app = service
    assert (
        client.post("/admin/shutdown", headers={"Authorization": "Bearer " + "a" * 40}).status_code
        == 200
    )
    assert app.state.worker.stop.is_set()


def test_service_rejects_missing_admin_secret(settings):
    with pytest.raises(SafetyError, match="ADMIN_TOKEN"):
        create_app(settings)


def test_dead_worker_requests_supervisor_exit(settings):
    class CrashingWorker(WaitingWorker):
        def run(self):
            raise RuntimeError("Sensitive exception detail must not be logged")

    settings.accessflow_request_type_ids = "12"
    settings.accessflow_admin_token = SecretStr("b" * 40)
    app = create_app(settings, worker_factory=CrashingWorker)
    exiting = threading.Event()
    app.state.shutdown = exiting.set
    with TestClient(app) as client:
        assert exiting.wait(5)
        assert client.get("/health").status_code == 503
