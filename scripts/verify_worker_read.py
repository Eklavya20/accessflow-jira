"""A real Phase A read-only poll with a transport-level mutation guard."""

import json
from pathlib import Path

from accessflow.config import SafetyError, Settings
from accessflow.jira import JiraClient
from accessflow.persistence import issue_lock, now
from accessflow.worker import Worker
from accessflow.worker_store import WorkerStore


def main():
    settings = Settings()
    if not settings.accessflow_dry_run or settings.accessflow_worker_write_enabled:
        raise SafetyError("Live read verification requires both dry-run safeguards")
    trace = []

    def guard(request):
        if request.method != "GET":
            raise SafetyError("Read acceptance forbids every Jira mutation")
        entry = {"method": request.method, "path": request.url.path, "status": None}
        trace.append(entry)
        request.extensions["verification_entry"] = entry

    def response(response):
        response.request.extensions["verification_entry"]["status"] = response.status_code

    started = now()
    with issue_lock(settings.database_path(), settings.jira_site_url, "polling-worker"):
        with JiraClient(settings) as client:
            client.http.event_hooks = {"request": [guard], "response": [response]}
            Worker(settings).poll(client)
    with WorkerStore(settings.database_path()) as store:
        report = {
            "started_at": started,
            "finished_at": now(),
            "requests": trace,
            "overview": store.overview(settings.jira_site_url),
            "writes": 0,
        }
    path = Path("reports/milestone3-initial-poll.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "requests": len(trace),
                "writes": 0,
                "summary": report["overview"]["runtime"]["last_poll_summary"],
            }
        )
    )


if __name__ == "__main__":
    main()
