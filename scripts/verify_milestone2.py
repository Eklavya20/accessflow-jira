"""Live acceptance for the three specifically approved internal AIS triage comments.

Only the first pass may send one exact POST per ticket. Same-process repeats,
fresh-process repeats and final inspection prohibit every remote write.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from accessflow.config import SafetyError, Settings
from accessflow.domain import digest
from accessflow.jira import JiraClient, JiraError
from accessflow.persistence import Store
from accessflow.processor import process, verify_remote

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "milestone2-live.json"
APPROVED_HASHES = {
    "AIS-1": "67e604786af91401977dcf32595bbd94b50503a45bc99c3bc04bf5935047850a",
    "AIS-2": "a4df22633205300321ab6e178fa4ca18b2c04e328df6f1902689a2bec2de5408",
    "AIS-3": "dd25763d9af360ac1a133616f4d7454b895516add18d6c8a7c3daa60bd590c14",
}
EXPECTED_IDS = {"AIS-1": "10006", "AIS-2": "10007", "AIS-3": "10008"}
EXPECTED_OUTCOMES = {
    "AIS-1": "privileged_review",
    "AIS-2": "ready_for_human_fulfillment",
    "AIS-3": "needs_information",
}


def authorization():
    settings = Settings()
    manifest = json.loads((ROOT / "reports/milestone2-approved.json").read_text(encoding="utf-8"))
    proposals = {p["issue_key"]: p for p in manifest["proposals"]}
    if (
        settings.jira_project_key != "AIS"
        or settings.allowed_projects != {"AIS"}
        or settings.jira_project_id != "10001"
        or settings.jira_service_desk_id != "2"
        or manifest.get("approved") is not True
        or set(proposals) != set(APPROVED_HASHES)
        or len(manifest["proposals"]) != 3
    ):
        raise SafetyError("Approval or sandbox configuration does not match the authorized scope")
    for key, proposal in proposals.items():
        if (
            proposal["issue_id"] != EXPECTED_IDS[key]
            or proposal.get("public") is not False
            or proposal["comment_sha256"] != APPROVED_HASHES[key]
            or hashlib.sha256(proposal["proposed_comment"].encode()).hexdigest()
            != APPROVED_HASHES[key]
            or not proposal["proposed_comment"].endswith(
                "[accessflow-triage:v1:" + proposal["operation_key"] + "]"
            )
        ):
            raise SafetyError("The approved exact comment body/hash/target does not match")
    return settings, proposals


def guarded_client(settings, proposals, trace, context, budgets):
    client = JiraClient(settings)
    prefix = client.http.base_url.path.rstrip("/")
    by_id = {p["issue_id"]: p for p in proposals.values()}

    def guard(request):
        path = request.url.path
        if prefix:
            if not path.startswith(prefix + "/"):
                raise SafetyError("Unexpected gateway prefix")
            path = path[len(prefix) :]
        entry = {"phase": context["phase"], "method": request.method, "path": path}
        trace.append(entry)
        request.extensions["accessflow_verification_entry"] = entry
        if request.method == "GET":
            allowed = {
                "/rest/api/3/myself",
                "/rest/api/3/mypermissions",
                "/rest/servicedeskapi/servicedesk/2",
                "/rest/servicedeskapi/servicedesk/2/requesttype/9",
                "/rest/servicedeskapi/servicedesk/2/requesttype/10",
                *["/rest/api/3/issue/" + key for key in proposals],
                *["/rest/servicedeskapi/request/" + issue_id for issue_id in by_id],
                *["/rest/servicedeskapi/request/" + issue_id + "/comment" for issue_id in by_id],
            }
            comment_match = re.fullmatch(
                r"/rest/servicedeskapi/request/([0-9]+)/comment/[0-9]+", path
            )
            if path in allowed or (comment_match and comment_match[1] in by_id):
                return
            entry["blocked"] = True
            raise SafetyError("Read outside the three-ticket verification scope blocked")
        match = re.fullmatch(r"/rest/servicedeskapi/request/([0-9]+)/comment", path)
        proposal = by_id.get(match[1]) if match else None
        if (
            context["phase"] != "initial_write"
            or request.method != "POST"
            or not proposal
            or budgets.get(proposal["issue_id"], 0) != 1
            or json.loads(request.content)
            != {"body": proposal["proposed_comment"], "public": False}
        ):
            entry["blocked"] = True
            raise SafetyError("Unapproved, duplicate or non-comment remote mutation blocked")
        budgets[proposal["issue_id"]] = 0

    def response(response):
        entry = response.request.extensions.get("accessflow_verification_entry")
        if entry is not None:
            entry["http_status"] = response.status_code

    client.http.event_hooks["request"].append(guard)
    client.http.event_hooks["response"].append(response)
    return client


def snapshot(client, proposal):
    key, issue_id = proposal["issue_key"], proposal["issue_id"]
    issue, _ = client.target(key)
    if str(issue["id"]) != issue_id:
        raise SafetyError("Actual issue identity differs from approved target")
    detail = client.get(f"/rest/api/3/issue/{key}", fields="project,status,assignee")
    comments = client.pages(f"/rest/servicedeskapi/request/{issue_id}/comment")
    body = proposal["proposed_comment"]
    marker = "[accessflow-triage:v1:" + proposal["operation_key"] + "]"
    matches = [c for c in comments if c.get("body") == body]
    if len(matches) > 1:
        raise SafetyError("Multiple exact matching triage comments exist")
    return {
        "status_id": str(detail["fields"]["status"]["id"]),
        "status": detail["fields"]["status"]["name"],
        "assignee_fingerprint": digest((detail["fields"].get("assignee") or {}).get("accountId")),
        "total_comments": len(comments),
        "exact_matches": len(matches),
        "marker_matches": sum(marker in c.get("body", "") for c in comments),
        "matching_comment_ids": [str(c["id"]) for c in matches],
        "matching_comments_internal": all(c.get("public") is False for c in matches),
    }


def exact_process(client, key, proposal, *, write):
    result = process(
        client, key, write=write, approved_sha256=proposal["comment_sha256"] if write else None
    )
    if (
        result.issue_id != proposal["issue_id"]
        or result.operation_key != proposal["operation_key"]
        or result.proposed_comment != proposal["proposed_comment"]
        or result.comment_sha256 != proposal["comment_sha256"]
        or result.decision.outcome != EXPECTED_OUTCOMES[key]
    ):
        raise SafetyError("Fresh request/decision differs from the authorized proposal")
    return result.model_dump()


def checkpoint(report):
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")


def restart_recheck(settings, proposals):
    trace, context = [], {"phase": "fresh_process_repeat"}
    results = {}
    with guarded_client(settings, proposals, trace, context, {}) as client:
        for key, proposal in proposals.items():
            results[key] = exact_process(client, key, proposal, write=True)
            if results[key]["write_status"] != "already_verified":
                raise SafetyError("Fresh process did not reuse the verified effect")
    return {"results": results, "requests": trace}


def run(settings, proposals):
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "passed": False,
        "before": {},
        "after": {},
        "preflight": {},
        "initial": {},
        "same_process_repeat": {},
        "requests": [],
    }
    budgets, context = {}, {"phase": "preflight"}
    try:
        with guarded_client(settings, proposals, report["requests"], context, budgets) as client:
            actor = client.identity()["accountId"]
            # All three fresh plans must match before the first remote mutation.
            for key, proposal in proposals.items():
                report["before"][key] = snapshot(client, proposal)
                report["preflight"][key] = exact_process(client, key, proposal, write=False)
                budgets[proposal["issue_id"]] = 0 if report["before"][key]["exact_matches"] else 1
            checkpoint(report)
            context["phase"] = "initial_write"
            for key, proposal in proposals.items():
                report["initial"][key] = exact_process(client, key, proposal, write=True)
                checkpoint(report)
            context["phase"] = "same_process_repeat"
            for key, proposal in proposals.items():
                report["same_process_repeat"][key] = exact_process(
                    client, key, proposal, write=True
                )
                if report["same_process_repeat"][key]["write_status"] != "already_verified":
                    raise SafetyError("Same-process repeat did not reuse the existing comment")
                checkpoint(report)
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--restart-recheck"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if child.returncode:
            (ROOT / "reports/milestone2-restart-error.json").write_text(
                child.stdout, encoding="utf-8"
            )
            raise SafetyError("Fresh-process verification failed; inspect local evidence")
        report["fresh_process_repeat"] = json.loads(child.stdout)
        checkpoint(report)
        context["phase"] = "final_read_back"
        with guarded_client(settings, proposals, report["requests"], context, {}) as client:
            for key, proposal in proposals.items():
                report["after"][key] = snapshot(client, proposal)
                verify_remote(
                    client,
                    proposal["issue_id"],
                    report["initial"][key]["comment_id"],
                    proposal["proposed_comment"],
                    actor,
                )
        with Store(settings.database_path()) as store:
            report["persisted"] = {
                key: {
                    "state": store.operation(p["operation_key"])["state"],
                    "comment_id": store.operation(p["operation_key"])["comment_id"],
                    "audit_events": len(store.history(settings.jira_site_url, key, limit=1000)),
                }
                for key, p in proposals.items()
            }
        posts = [r for r in report["requests"] if r["method"] == "POST"]
        child_posts = [
            r for r in report["fresh_process_repeat"]["requests"] if r["method"] != "GET"
        ]
        report["post_attempts"] = len(posts)
        report["post_responses_201"] = sum(r.get("http_status") == 201 for r in posts)
        report["repeat_post_attempts"] = sum(r["phase"] != "initial_write" for r in posts)
        report["fresh_process_post_attempts"] = len(child_posts)
        report["all_read_back_internal"] = all(
            v["matching_comments_internal"] and v["exact_matches"] == v["marker_matches"] == 1
            for v in report["after"].values()
        )
        expected_posts = sum(1 - v["exact_matches"] for v in report["before"].values())
        report["passed"] = (
            report["all_read_back_internal"]
            and len(posts) == expected_posts
            and report["post_responses_201"] == expected_posts
            and report["repeat_post_attempts"] == 0
            and not child_posts
            and all(not r.get("blocked") for r in report["requests"])
            and all(
                report["initial"][key]["comment_id"]
                == report["same_process_repeat"][key]["comment_id"]
                == report["fresh_process_repeat"]["results"][key]["comment_id"]
                == report["persisted"][key]["comment_id"]
                and report["persisted"][key]["state"] == "verified"
                and report["before"][key]["status_id"] == report["after"][key]["status_id"]
                and report["before"][key]["assignee_fingerprint"]
                == report["after"][key]["assignee_fingerprint"]
                and report["after"][key]["total_comments"]
                == report["before"][key]["total_comments"]
                + (1 - report["before"][key]["exact_matches"])
                for key in proposals
            )
        )
        if not report["passed"]:
            raise SafetyError("Live acceptance assertions failed; do not mark Milestone 2 passed")
    except Exception as exc:
        report["error"] = (
            str(exc) if isinstance(exc, (JiraError, SafetyError)) else type(exc).__name__
        )
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        report["local_dry_run_default"] = Settings().accessflow_dry_run
        checkpoint(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart-recheck", action="store_true")
    args = parser.parse_args()
    settings, proposals = authorization()
    if args.restart_recheck:
        print(json.dumps(restart_recheck(settings, proposals)))
        return 0
    report = run(settings, proposals)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "initial": {
                    key: {
                        "comment_id": value["comment_id"],
                        "write_status": value["write_status"],
                        "outcome": value["decision"]["outcome"],
                    }
                    for key, value in report["initial"].items()
                },
                "post_attempts": report.get("post_attempts"),
                "post_responses_201": report.get("post_responses_201"),
                "same_process_repeat_post_attempts": report.get("repeat_post_attempts"),
                "fresh_process_repeat_post_attempts": report.get("fresh_process_post_attempts"),
                "all_read_back_internal": report.get("all_read_back_internal"),
                "before": report["before"],
                "after": report["after"],
                "persisted": report.get("persisted"),
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
        print(
            json.dumps({"event": "milestone2_verification_blocked", "reason": type(error).__name__})
        )
        raise SystemExit(1) from None
