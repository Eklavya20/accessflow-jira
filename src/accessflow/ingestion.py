from accessflow.config import SafetyError
from accessflow.domain import Policy, RequestInput
from accessflow.jira import JiraClient
from accessflow.parsing import formatted_values, plain_text


def ingest(client: JiraClient, key: str, policy: Policy) -> RequestInput:
    issue, request = client.target(key)
    detail = client.get(f"/rest/api/3/issue/{key}", fields="summary,description,project,status")
    project = detail["fields"]["project"]
    if (
        str(detail.get("id")) != str(issue["id"])
        or project.get("key") != client.settings.jira_project_key
        or str(project.get("id")) != client.settings.jira_project_id
    ):
        raise SafetyError("Request scope changed during ingestion")
    type_id = str(request["requestTypeId"])
    if not type_id.isdigit():
        raise SafetyError("Invalid request type ID")
    request_type = client.get(
        f"/rest/servicedeskapi/servicedesk/{client.settings.jira_service_desk_id}/requesttype/{type_id}"
    )
    fields = detail["fields"]
    request_values = {v["fieldId"]: v.get("value") for v in request.get("requestFieldValues", [])}
    requester_id = request.get("reporter", {}).get("accountId")
    comments = client.pages(f"/rest/servicedeskapi/request/{issue['id']}/comment")
    updates = []
    # The documented collection is ordered by creation; sort by stable numeric ID
    # so pagination boundaries never change which correction takes precedence.
    for comment in sorted(comments, key=lambda c: int(c["id"])):
        body = comment.get("body", "")
        if (
            requester_id
            and comment.get("public") is True
            and comment.get("author", {}).get("accountId") == requester_id
            and not body.startswith("AccessFlow ")
            and any(formatted_values(body).values())
        ):
            updates.append(body)
    return RequestInput(
        issue_id=str(issue["id"]),
        issue_key=key,
        request_type_id=type_id,
        request_type=request_type["name"],
        status=fields.get("status", {}).get("name")
        or request.get("currentStatus", {}).get("status", "Unknown"),
        summary=fields.get("summary") or request.get("summary", ""),
        description=plain_text(fields.get("description") or request_values.get("description", "")),
        requester_id=requester_id,
        mapped_fields={
            field: plain_text(request_values.get(field_id))
            for field, field_id in policy.field_mapping.items()
        },
        requester_updates=updates,
    )
