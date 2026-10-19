"""Verify the already-approved AIS-1 comment and duplicate prevention on real Jira.

This intentionally permits at most one exact POST in the initial process and no
POST in the fresh-process recheck. It leaves the local .env in dry-run mode.
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from accessflow.config import SafetyError, Settings
from accessflow.jira import JiraClient, JiraError
from accessflow.probe import probe_comment

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "milestone1-live.json"


def approved_settings() -> Settings:
    settings = Settings()
    approval = json.loads((ROOT / "reports" / "comment-approval.json").read_text(encoding="utf-8"))
    if (
        settings.require_target() != "AIS-1"
        or settings.allowed_projects != {"AIS"}
        or approval.get("approved") is not True
        or approval.get("issue_key") != "AIS-1"
        or approval.get("visibility") != "internal"
        or not approval.get("body")
        or approval["body"] != settings.accessflow_probe_comment_body
    ):
        raise SafetyError("Exact AIS-1 internal-comment authorization does not match configuration")
    # The user approved this one operation. Persisted defaults remain read-only.
    settings.accessflow_dry_run = False
    return settings


def guarded_client(settings: Settings, trace: list, *, allow_one_post: bool) -> JiraClient:
    client = JiraClient(settings)
    prefix = client.http.base_url.path.rstrip("/")
    post_count = 0

    def guard(request):
        nonlocal post_count
        path = request.url.path
        if prefix:
            if not path.startswith(prefix + "/"):
                raise SafetyError("Unexpected API gateway prefix")
            path = path[len(prefix) :]
        trace.append({"method": request.method, "path": path})
        if request.method == "GET":
            allowed = {
                "/rest/api/3/myself",
                "/rest/api/3/issue/AIS-1",
                "/rest/api/3/mypermissions",
                f"/rest/servicedeskapi/servicedesk/{settings.jira_service_desk_id}",
                "/rest/servicedeskapi/request/10006",
                "/rest/servicedeskapi/request/10006/comment",
            }
            if path not in allowed and not re.fullmatch(
                r"/rest/servicedeskapi/request/10006/comment/[0-9]+", path
            ):
                raise SafetyError("Read outside the designated verification scope was blocked")
            return
        if (
            not allow_one_post
            or post_count != 0
            or request.method != "POST"
            or path != "/rest/servicedeskapi/request/10006/comment"
            or json.loads(request.content)
            != {"body": settings.accessflow_probe_comment_body, "public": False}
        ):
            raise SafetyError("Unexpected or duplicate Jira write blocked before sending")
        post_count += 1

    client.http.event_hooks["request"].append(guard)
    return client


def checkpoint(report: dict) -> None:
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")


def run() -> dict:
    settings = approved_settings()
    report = {"started_at": datetime.now(UTC).isoformat(), "issue_key": "AIS-1", "passed": False}
    trace = []
    try:
        with guarded_client(settings, trace, allow_one_post=True) as client:
            client.identity()
            issue, request = client.target()
            if str(issue["id"]) != "10006" or str(request["requestTypeId"]) != "10":
                raise SafetyError("Designated issue or request type changed")
            before = client.get("/rest/api/3/issue/AIS-1", fields="project,status")
            before_comments = client.pages("/rest/servicedeskapi/request/10006/comment")
            body = settings.accessflow_probe_comment_body
            matches_before = [c for c in before_comments if c.get("body") == body]
            if len(matches_before) > 1:
                raise SafetyError("Duplicate matching comments already exist; inspection required")
            report.update(
                {
                    "authentication": "verified",
                    "jsm_request_read": "verified",
                    "issue_id": str(issue["id"]),
                    "status_before": before["fields"]["status"]["name"],
                    "matching_comments_before": len(matches_before),
                    "requests": trace,
                }
            )
            checkpoint(report)
            report["first_run"] = probe_comment(client, confirmed_key="AIS-1", public=False)
            checkpoint(report)
            report["same_process_repeat"] = probe_comment(
                client, confirmed_key="AIS-1", public=False
            )
            checkpoint(report)
        # A new interpreter and HTTP client reopen the same durable SQLite journal.
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--restart-recheck"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if child.returncode:
            raise SafetyError("Fresh-process recheck failed; inspect local verification evidence")
        report["fresh_process_repeat"] = json.loads(child.stdout)
        with guarded_client(settings, trace, allow_one_post=False) as client:
            after = client.get("/rest/api/3/issue/AIS-1", fields="project,status")
            after_comments = client.pages("/rest/servicedeskapi/request/10006/comment")
        matches_after = [c for c in after_comments if c.get("body") == body]
        report["status_after"] = after["fields"]["status"]["name"]
        report["matching_comments_after"] = len(matches_after)
        report["post_attempts"] = sum(r["method"] == "POST" for r in trace)
        report["fresh_process_post_attempts"] = sum(
            r["method"] == "POST" for r in report["fresh_process_repeat"]["requests"]
        )
        with sqlite3.connect(settings.database_path()) as db:
            rows = db.execute(
                "SELECT state, comment_id, public, body_sha256 FROM connectivity_probes"
            ).fetchall()
        report["persistent_records"] = [
            {"state": row[0], "comment_id": row[1], "public": bool(row[2]), "body_sha256": row[3]}
            for row in rows
        ]
        comment_id = report["first_run"]["comment_id"]
        report["passed"] = (
            report["first_run"]["write"]
            in ("created_and_verified", "already_verified", "reconciled")
            and report["same_process_repeat"]["write"] == "already_verified"
            and report["fresh_process_repeat"]["result"]["write"] == "already_verified"
            and report["same_process_repeat"]["comment_id"] == comment_id
            and report["fresh_process_repeat"]["result"]["comment_id"] == comment_id
            and len(matches_after) == 1
            and str(matches_after[0]["id"]) == comment_id
            and matches_after[0].get("public") is False
            and report["status_before"] == report["status_after"]
            and report["post_attempts"] == (0 if matches_before else 1)
            and report["fresh_process_post_attempts"] == 0
            and any(r[0] == "verified" and r[1] == comment_id and r[2] == 0 for r in rows)
        )
        if not report["passed"]:
            raise SafetyError(
                "Live verification assertions failed; do not mark the milestone passed"
            )
    except Exception as exc:
        report["error"] = (
            str(exc) if isinstance(exc, (SafetyError, JiraError)) else type(exc).__name__
        )
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        checkpoint(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart-recheck", action="store_true")
    args = parser.parse_args()
    if args.restart_recheck:
        settings = approved_settings()
        trace = []
        with guarded_client(settings, trace, allow_one_post=False) as client:
            result = probe_comment(client, confirmed_key="AIS-1", public=False)
        print(json.dumps({"result": result, "requests": trace}))
        return 0
    report = run()
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "first_run": report.get("first_run"),
                "same_process_repeat": report.get("same_process_repeat"),
                "fresh_process_repeat": report.get("fresh_process_repeat", {}).get("result"),
                "matching_comments_before": report.get("matching_comments_before"),
                "matching_comments_after": report.get("matching_comments_after"),
                "post_attempts": report.get("post_attempts"),
                "fresh_process_post_attempts": report.get("fresh_process_post_attempts"),
                "status_before": report.get("status_before"),
                "status_after": report.get("status_after"),
                "error": report.get("error"),
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"event": "live_verification_blocked", "reason": type(error).__name__}))
        raise SystemExit(1) from None
