"""Read-only diagnostics for the configured sandbox; never posts comments."""

import argparse
import base64
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from dotenv import set_key

from accessflow.config import Settings
from accessflow.jira import JiraClient, JiraError


def text_content(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(text_content(child) for child in value)
    if isinstance(value, dict):
        own = value.get("text", "")
        suffix = "\n" if value.get("type") in ("paragraph", "heading", "hardBreak") else ""
        return own + text_content(value.get("content", [])) + suffix
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-identity",
        action="store_true",
        help="Skip an identity endpoint already known to lack token scopes",
    )
    args = parser.parse_args()
    settings = Settings()
    key = settings.jira_test_issue_key
    settings.assert_issue_key(key)
    token = settings.jira_api_token.get_secret_value()
    basic = base64.b64encode(f"{settings.jira_email}:{token}".encode()).decode()

    def redact(value) -> str:
        result = str(value)
        for secret in (token, basic, settings.jira_email):
            result = result.replace(secret, "[REDACTED]")
        return result[:1500]

    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "mode": "read_only",
        "api_base": settings.api_base,
        "checks": {},
        "writes": 0,
    }
    with JiraClient(settings) as client:

        def get(name, path, **params):
            try:
                data = client.get(path, **params)
                report["checks"][name] = {"status": "verified", "http_status": 200}
                return data
            except JiraError as exc:
                report["checks"][name] = {
                    "status": "blocked",
                    "http_status": exc.status,
                    "reason": str(exc),
                }
                return None

        if args.skip_identity:
            report["checks"]["identity"] = {
                "status": "not_attempted",
                "note": "Skipped by operator to avoid a known denial",
            }
        else:
            identity = get("identity", "/rest/api/3/myself")
            if identity:
                report["identity_active"] = identity.get("active") is True
        project = get("project", f"/rest/api/3/project/{settings.jira_project_key}")
        if project and project.get("key") == settings.jira_project_key:
            report["project"] = {k: project.get(k) for k in ("id", "key", "projectTypeKey")}
            set_key(".env", "JIRA_PROJECT_ID", str(project["id"]))
        issue = get(
            "issue", f"/rest/api/3/issue/{key}", fields="summary,description,project,status"
        )
        if issue:
            fields = issue["fields"]
            actual_project = fields["project"]
            if actual_project.get("key") != settings.jira_project_key or (
                project and str(actual_project["id"]) != str(project["id"])
            ):
                raise ValueError("Actual issue project mismatch")
            description = text_content(fields.get("description"))
            extracted = {}
            for label in ("Application", "Access level", "Business justification"):
                match = re.search(rf"(?im)^\s*{label}\s*:\s*(.+)$", description)
                extracted[label] = redact(match.group(1).strip()) if match else None
            report["issue"] = {
                "id": issue["id"],
                "key": issue["key"],
                "summary": redact(fields.get("summary")),
                "status": fields.get("status", {}).get("name"),
                "extracted": extracted,
                "description_present": bool(description.strip()),
                "sandbox_notice_present": "sandbox" in description.lower(),
                "no_actual_access_notice_present": bool(
                    re.search(
                        r"no\s+(?:actual\s+)?access\s+(?:should\s+be\s+)?granted", description, re.I
                    )
                ),
            }
            permissions = get(
                "permissions",
                "/rest/api/3/mypermissions",
                issueId=issue["id"],
                permissions="BROWSE_PROJECTS,ADD_COMMENTS,EDIT_ISSUES,"
                "TRANSITION_ISSUES,ASSIGN_ISSUES",
            )
            if permissions:
                report["permissions"] = {
                    k: v.get("havePermission") is True
                    for k, v in permissions.get("permissions", {}).items()
                }
            transitions = get(
                "transitions",
                f"/rest/api/3/issue/{issue['id']}/transitions",
                expand="transitions.fields",
            )
            if transitions:
                report["transitions"] = [
                    {
                        "id": t["id"],
                        "name": t.get("name"),
                        "destination": t.get("to", {}).get("name"),
                    }
                    for t in transitions.get("transitions", [])
                ]
            editable = get("edit_metadata", f"/rest/api/3/issue/{issue['id']}/editmeta")
            if editable:
                report["editable_fields"] = [
                    {"id": k, "name": v.get("name")} for k, v in editable.get("fields", {}).items()
                ]
        desks = get("service_desks", "/rest/servicedeskapi/servicedesk", start=0, limit=50)
        if desks:
            matches = [
                d
                for d in desks.get("values", [])
                if d.get("projectKey") == settings.jira_project_key
            ]
            report["desk_inventory_complete"] = desks.get("isLastPage") is True
            if matches:
                desk = matches[0]
                report["service_desk"] = {k: desk.get(k) for k in ("id", "projectId", "projectKey")}
                set_key(".env", "JIRA_SERVICE_DESK_ID", str(desk["id"]))
                types = get(
                    "request_types",
                    f"/rest/servicedeskapi/servicedesk/{desk['id']}/requesttype",
                    start=0,
                    limit=50,
                )
                if types:
                    report["request_types"] = [
                        {"id": t["id"], "name": t.get("name")} for t in types.get("values", [])
                    ]
                    report["type_inventory_complete"] = types.get("isLastPage") is True
                    for request_type in types.get("values", []):
                        if request_type.get("name", "").casefold() != "request admin access":
                            continue
                        required = get(
                            "request_type_fields",
                            f"/rest/servicedeskapi/servicedesk/{desk['id']}/"
                            f"requesttype/{request_type['id']}/field",
                        )
                        if required:
                            report["request_type_fields"] = [
                                {k: f.get(k) for k in ("fieldId", "name", "required")}
                                for f in required.get("requestTypeFields", [])
                            ]
        request = get("jsm_request", f"/rest/servicedeskapi/request/{key}")
        if request:
            report["jsm_request"] = {
                k: request.get(k) for k in ("issueId", "issueKey", "serviceDeskId", "requestTypeId")
            }
        # Comment read/write and approvals require absent user/approval scopes.
        # Avoid known-ineligible probes until the user updates the token.
    output = json.dumps(report, indent=2)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/live-read.json").write_text(output, encoding="utf-8")
    print(output)
    return 0 if issue else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError):
        print(
            json.dumps({"event": "read_diagnostics_failed", "reason": "Configuration/data error"})
        )
        raise SystemExit(1) from None
