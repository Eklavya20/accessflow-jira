from pathlib import Path

import httpx
import pytest

from accessflow.config import Settings
from accessflow.jira import JiraClient


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        jira_site_url="https://sandbox.atlassian.net",
        jira_email="tester@example.invalid",
        jira_api_token="unit-test-token",
        jira_token_kind="unscoped",
        jira_project_key="AFTEST",
        jira_project_id="10001",
        jira_service_desk_id="7",
        jira_allowed_project_keys="AFTEST",
        jira_test_issue_key="AFTEST-1",
        accessflow_probe_comment_body="",
        jira_query_approvals=True,
        database_url=f"sqlite:///{tmp_path / 'journal.db'}",
    )


class SandboxAPI:
    """Isolated unit-test fixture only. Never used by application or live acceptance."""

    def __init__(self):
        self.calls = []
        self.comments = []
        self.posts = 0
        self.post_failure = None
        self.permissions = True
        self.project_key = "AFTEST"
        self.approval_status = 200
        self.wrong_visibility = False

    def __call__(self, request):
        import json

        self.calls.append(request)
        path = request.url.path
        if path.endswith("/myself"):
            data = {
                "accountId": "test-account",
                "active": True,
                "emailAddress": "private@example.invalid",
            }
        elif path.endswith("/project/search"):
            data = {
                "values": [{"id": "10001", "key": "AFTEST", "name": "Test sandbox"}],
                "isLast": True,
            }
        elif path == "/rest/servicedeskapi/servicedesk":
            data = self.page([{"id": "7", "projectId": "10001", "projectKey": "AFTEST"}])
        elif path.endswith("/servicedesk/7"):
            data = {"id": "7", "projectId": "10001", "projectKey": "AFTEST"}
        elif path.endswith("/requesttype"):
            data = self.page([{"id": "12", "name": "Application access"}])
        elif path.endswith("/requesttype/12/field"):
            data = {
                "requestTypeFields": [{"fieldId": "summary", "name": "Summary", "required": True}]
            }
        elif path == "/rest/api/3/issue/AFTEST-1":
            data = {
                "id": "9001",
                "key": "AFTEST-1",
                "fields": {
                    "project": {"id": "10001", "key": self.project_key},
                    "status": {"id": "10"},
                },
            }
        elif path == "/rest/servicedeskapi/request/9001":
            data = {
                "issueId": "9001",
                "issueKey": "AFTEST-1",
                "serviceDeskId": "7",
                "requestTypeId": "12",
                "summary": "Private request content",
                "requestFieldValues": [{"fieldId": "summary", "value": "Private content"}],
            }
        elif path.endswith("/mypermissions"):
            data = {
                "permissions": {
                    k: {"havePermission": self.permissions}
                    for k in request.url.params["permissions"].split(",")
                }
            }
        elif path.endswith("/transitions"):
            data = {"transitions": [{"id": "21", "name": "Review", "to": {"id": "11"}}]}
        elif path.endswith("/editmeta"):
            data = {"fields": {"labels": {"name": "Labels", "required": False}}}
        elif path.endswith("/approval"):
            return httpx.Response(self.approval_status, json=self.page([]))
        elif path.endswith("/comment"):
            if request.method == "POST":
                self.posts += 1
                payload = json.loads(request.content)
                comment = {
                    "id": str(len(self.comments) + 1),
                    **payload,
                    "author": {"accountId": "test-account"},
                }
                if self.wrong_visibility:
                    comment["public"] = not comment["public"]
                self.comments.append(comment)
                if self.post_failure == "timeout":
                    raise httpx.ReadTimeout("sensitive remote detail", request=request)
                if self.post_failure:
                    return httpx.Response(self.post_failure, json={})
                return httpx.Response(201, json=comment)
            data = self.page(self.comments)
        elif "/comment/" in path:
            matches = [c for c in self.comments if c["id"] == path.rsplit("/", 1)[1]]
            return httpx.Response(200 if matches else 404, json=matches[0] if matches else {})
        else:
            pytest.fail(f"Unexpected request in unit test: {request.method} {path}")
        return httpx.Response(200, json=data)

    @staticmethod
    def page(values):
        return {"values": values, "isLastPage": True}


@pytest.fixture
def sandbox():
    return SandboxAPI()


@pytest.fixture
def client(settings, sandbox):
    with JiraClient(
        settings, transport=httpx.MockTransport(sandbox), sleep=lambda _: None
    ) as value:
        yield value


@pytest.fixture
def workflow(settings, sandbox):
    settings.accessflow_policy_path = Path(__file__).resolve().parents[1] / "config/policy.json"
    sandbox.description = (
        "Application: GitHub\nAccess level: Read-only\n"
        "Business justification: Review project documentation."
    )
    sandbox.reporter = "test-requester"
    sandbox.read_failures = []
    sandbox.deny_post = None
    sandbox.current_status = "Waiting for support"

    def handler(request):
        if request.method == "POST" and sandbox.deny_post:
            sandbox.calls.append(request)
            sandbox.posts += 1
            return httpx.Response(sandbox.deny_post, json={})
        if request.url.path == "/rest/api/3/issue/AFTEST-1" and sandbox.read_failures:
            status = sandbox.read_failures.pop(0)
            return httpx.Response(status, json={})
        if request.url.path.endswith("/requesttype/12"):
            sandbox.calls.append(request)
            return httpx.Response(200, json={"id": "12", "name": "Application access"})
        response = sandbox(request)
        data = response.json()
        if request.url.path == "/rest/api/3/issue/AFTEST-1":
            data["fields"].update(summary="Access request", description=sandbox.description)
            data["fields"]["status"]["name"] = sandbox.current_status
        elif request.url.path == "/rest/servicedeskapi/request/9001":
            data["reporter"] = {"accountId": sandbox.reporter}
        return httpx.Response(response.status_code, json=data, headers=response.headers)

    with JiraClient(
        settings, transport=httpx.MockTransport(handler), sleep=lambda _: None
    ) as client:
        yield client, sandbox
