"""Independent GET-only evidence for the approved AIS-5 automatic-write test.

This observer never invokes the processor, schedules a job, or writes to Jira.
"""

import argparse
import json
from pathlib import Path

from manage_service import request

from accessflow.config import SafetyError, Settings
from accessflow.domain import digest
from accessflow.jira import JiraClient, JiraError
from accessflow.persistence import now
from accessflow.processor import verify_remote
from accessflow.worker_store import WorkerStore

REPORT = Path("reports/milestone3-automatic-write.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["before", "after", "repeat", "restart", "disabled"])
    stage = parser.parse_args().stage
    settings = Settings()
    if (
        settings.jira_project_key != "AIS"
        or settings.allowed_projects != {"AIS"}
        or settings.jira_project_id != "10001"
        or settings.jira_service_desk_id != "2"
    ):
        raise SafetyError("Live observer is restricted to the AIS acceptance sandbox")
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    if stage in report:
        raise SafetyError("Evidence stage already captured; preserve the original record")
    trace = []

    def guard(req):
        if req.method != "GET":
            raise SafetyError("Independent observer forbids every Jira mutation")
        entry = {"method": "GET", "path": req.url.path}
        trace.append(entry)
        req.extensions["observer_entry"] = entry

    def response(res):
        res.request.extensions["observer_entry"]["status"] = res.status_code

    snapshot = {}
    with JiraClient(settings) as client:
        client.http.event_hooks = {"request": [guard], "response": [response]}
        for key in ["AIS-1", "AIS-2", "AIS-3", "AIS-4", "AIS-5"]:
            try:
                issue = client.get("/rest/api/3/issue/" + key, fields="project,status,assignee")
            except JiraError as exc:
                if key == "AIS-5" and stage == "before" and exc.status == 404:
                    snapshot[key] = {"absent": True}
                    continue
                raise
            project = issue["fields"]["project"]
            if issue["key"] != key or project["key"] != "AIS" or str(project["id"]) != "10001":
                raise SafetyError("Unexpected issue scope during independent read-back")
            comments = client.pages(f"/rest/servicedeskapi/request/{issue['id']}/comment")
            snapshot[key] = {
                "issue_id": str(issue["id"]),
                "status_id": str(issue["fields"]["status"]["id"]),
                "assignee_fingerprint": digest(
                    (issue["fields"].get("assignee") or {}).get("accountId")
                ),
                "comment_ids": [str(c["id"]) for c in comments],
                "comment_count": len(comments),
            }
            if key == "AIS-5":
                if stage == "before":
                    raise SafetyError("AIS-5 already exists; do not activate the new-request test")
                with WorkerStore(settings.database_path()) as store:
                    result = store.latest(settings.jira_site_url, key)
                    job = store.job(settings.jira_site_url, str(issue["id"]))
                    budget = [
                        dict(row) for row in store.db.execute("SELECT * FROM worker_write_budget")
                    ]
                    audit = store.history(settings.jira_site_url, key)
                if (
                    not job
                    or job["state"] != "done"
                    or not job["comment_id"]
                    or result["write_status"] != "verified"
                ):
                    raise SafetyError("The autonomous worker has not verified its action yet")
                verify_remote(
                    client,
                    str(issue["id"]),
                    job["comment_id"],
                    result["proposed_comment"],
                    client.identity()["accountId"],
                )
                marker = "[accessflow-triage:v1:" + result["operation_key"] + "]"
                matches = [c for c in comments if marker in c.get("body", "")]
                if (
                    len(matches) != 1
                    or matches[0].get("public") is not False
                    or matches[0]["body"] != result["proposed_comment"]
                ):
                    raise SafetyError("Exact internal automatic comment count did not verify")
                before = [e["details"] for e in audit if e["event"] == "worker_before_comment"]
                if (
                    len(before) != 1
                    or before[0]["status_id"] != snapshot[key]["status_id"]
                    or before[0]["assignee_fingerprint"] != snapshot[key]["assignee_fingerprint"]
                ):
                    raise SafetyError("Pre-comment status/assignment did not match read-back")
                snapshot[key].update(
                    comment_id=job["comment_id"],
                    public=False,
                    exact_matches=1,
                    comment_sha256=result["comment_sha256"],
                    operation_key=result["operation_key"],
                    body=result["proposed_comment"],
                    job=job,
                    budget=budget,
                    audit=audit,
                )
    status = request(settings, "GET", "/admin/status")
    health = request(settings, "GET", "/health")
    if stage != "before":
        for key in ["AIS-1", "AIS-2", "AIS-3", "AIS-4"]:
            if snapshot[key] != report["before"]["tickets"][key]:
                raise SafetyError("A protected acceptance ticket changed; inspect evidence")
        if stage != "after":
            initial = report["after"]["tickets"]["AIS-5"]
            for key in [
                "comment_id",
                "comment_ids",
                "status_id",
                "assignee_fingerprint",
                "comment_sha256",
                "operation_key",
                "exact_matches",
            ]:
                if snapshot["AIS-5"][key] != initial[key]:
                    raise SafetyError("Repeat/restart changed the verified Jira action")
    report[stage] = {
        "observed_at": now(),
        "tickets": snapshot,
        "runtime": status["runtime"],
        "health": health,
        "requests": trace,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "stage": stage,
                "GETs": len(trace),
                "Jira_writes": 0,
                "AIS-5_comment_id": snapshot["AIS-5"].get("comment_id"),
                "health": health,
            }
        )
    )


if __name__ == "__main__":
    main()
