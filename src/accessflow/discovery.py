from datetime import UTC, datetime

from accessflow.config import SafetyError
from accessflow.jira import JiraClient, JiraError


def discover(client: JiraClient, *, check_target: bool = False) -> dict:
    client.identity()
    projects = client.pages("/rest/api/3/project/search", platform=True)
    desks = client.pages("/rest/servicedeskapi/servicedesk")
    report = {
        "observed_at": datetime.now(UTC).isoformat(),
        "authentication": "verified",
        "projects": [
            {k: p.get(k) for k in ("id", "key", "name", "projectTypeKey")} for p in projects
        ],
        "service_desks": [
            {k: d.get(k) for k in ("id", "projectId", "projectKey", "projectName")} for d in desks
        ],
        "target": "not_checked",
        "subscription": "not_verified: confirm plan in Atlassian administration",
        "write": "not_attempted",
        "milestone_1": "incomplete",
    }
    settings = client.settings
    # Inventory is metadata only. Detailed discovery is confined to allowlisted desks.
    report["request_types"] = []
    for desk in desks:
        if desk.get("projectKey") not in settings.allowed_projects:
            continue
        if settings.jira_service_desk_id and str(desk["id"]) != settings.jira_service_desk_id:
            continue
        types = client.pages(f"/rest/servicedeskapi/servicedesk/{desk['id']}/requesttype")
        for request_type in types:
            fields = client.get(
                f"/rest/servicedeskapi/servicedesk/{desk['id']}/requesttype/{request_type['id']}/field"
            )
            report["request_types"].append(
                {
                    "service_desk_id": str(desk["id"]),
                    "id": request_type["id"],
                    "name": request_type.get("name"),
                    "fields": [
                        {k: field.get(k) for k in ("fieldId", "name", "required", "jiraSchema")}
                        for field in fields.get("requestTypeFields", [])
                    ],
                }
            )
    if not check_target:
        return report
    issue, request = client.target()
    issue_id = str(issue["id"])
    permissions = client.permissions(issue_id)
    if not permissions["BROWSE_PROJECTS"]:
        raise SafetyError("Browse Projects permission is not confirmed for the test issue")
    report["target"] = {
        "issue_id": issue_id,
        "issue_key": issue["key"],
        "service_desk_id": request["serviceDeskId"],
        "request_type_id": request["requestTypeId"],
        "request_fields_present": [f["fieldId"] for f in request.get("requestFieldValues", [])],
        "permissions": permissions,
    }
    # Each optional capability reports its exact failure, never a fabricated fallback.
    probes = {
        "transitions": (
            f"/rest/api/3/issue/{issue_id}/transitions",
            {"expand": "transitions.fields"},
        ),
        "editable_fields": (f"/rest/api/3/issue/{issue_id}/editmeta", {}),
        "approvals": (f"/rest/servicedeskapi/request/{issue_id}/approval", {}),
    }
    report["capabilities"] = {}
    for name, (path, params) in probes.items():
        if name == "approvals" and not settings.jira_query_approvals:
            report["capabilities"][name] = {
                "read": "not_checked",
                "note": "Enable JIRA_QUERY_APPROVALS only with verified workflow and read scopes",
            }
            continue
        try:
            if name == "approvals":
                approvals = client.pages(path)
                detail = [
                    {"id": a.get("id"), "finalDecision": a.get("finalDecision")} for a in approvals
                ]
                note = "Empty results do not prove approvals are configured or licensed"
            else:
                raw = client.get(path, **params)
                detail = (
                    [
                        {
                            "id": t["id"],
                            "name": t.get("name"),
                            "to_status_id": t.get("to", {}).get("id"),
                            "required_fields": [
                                k for k, v in t.get("fields", {}).items() if v.get("required")
                            ],
                        }
                        for t in raw.get("transitions", [])
                    ]
                    if name == "transitions"
                    else [
                        {"id": k, "name": v.get("name"), "required": v.get("required")}
                        for k, v in raw.get("fields", {}).items()
                    ]
                )
                note = "Observed for this issue, identity, and current workflow state only"
            report["capabilities"][name] = {"read": "verified", "observed": detail, "note": note}
        except JiraError as exc:
            if exc.status == 401:
                raise
            report["capabilities"][name] = {
                "read": "unverified",
                "http_status": exc.status,
                "reason": str(exc),
            }
    report["comment_permissions"] = (
        "Add Comments reported; actual visibility/write must be tested separately"
        if permissions["ADD_COMMENTS"]
        else "Add Comments denied; write milestone blocked"
    )
    return report
