import random
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from accessflow.config import SafetyError, Settings


class JiraError(Exception):
    def __init__(self, message: str, status: int | None = None, retry_after: float = 0):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class UncertainWrite(JiraError):
    """A POST may have succeeded. Never automatically resend it."""


class JiraClient:
    def __init__(self, settings: Settings, *, transport=None, sleep=time.sleep):
        self.settings = settings
        self.sleep = sleep
        self.http = httpx.Client(
            base_url=settings.api_base + "/",
            auth=httpx.BasicAuth(settings.jira_email, settings.jira_api_token.get_secret_value()),
            headers={"Accept": "application/json", "User-Agent": "AccessFlow/0.1"},
            timeout=settings.jira_timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http.close()

    def retry_wait(self, response: httpx.Response | None, attempt: int) -> float:
        wait = min(2**attempt + random.uniform(0, 0.25), 30)
        header = response.headers.get("Retry-After") if response is not None else None
        if header:
            try:
                wait = max(0.0, float(header))
            except ValueError:
                try:
                    wait = max(
                        0.0, (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
                    )
                except (ValueError, TypeError, OverflowError):
                    pass
        if wait > self.settings.jira_max_retry_wait_seconds:
            raise JiraError(
                "Retry-After exceeds local wait budget; retry discovery later", 429, wait
            )
        return wait

    def request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        # Fixed local API paths only: credentials never follow a remote link or redirect.
        if not path.startswith("/rest/") or ".." in path or "?" in path or "#" in path:
            raise SafetyError("Only local Jira REST paths are accepted")
        write = method != "GET"
        if write and self.settings.accessflow_dry_run:
            raise SafetyError("Dry-run mode forbids Jira writes")
        attempts = 1 if write else self.settings.jira_read_attempts
        for attempt in range(attempts):
            response = None
            try:
                response = self.http.request(method, path.lstrip("/"), **kwargs)
            except httpx.TransportError:
                if write:
                    raise UncertainWrite(
                        "Write transport failed; reconcile before any retry"
                    ) from None
                if attempt + 1 == attempts:
                    raise JiraError("Jira transport failed after bounded read attempts") from None
                self.sleep(self.retry_wait(None, attempt))
                continue
            status = response.status_code
            if status == 429 or 500 <= status <= 599:
                if write:
                    retry_after = 0
                    if status == 429:
                        try:
                            retry_after = self.retry_wait(response, attempt)
                        except JiraError as exc:
                            retry_after = exc.retry_after
                    raise UncertainWrite(
                        "Write returned an uncertain response; reconcile", status, retry_after
                    )
                if attempt + 1 < attempts:
                    self.sleep(self.retry_wait(response, attempt))
                    continue
            if not 200 <= status < 300:
                # Do not include raw response bodies, URLs, or authentication details.
                retry_after = 0
                if status == 429:
                    try:
                        retry_after = self.retry_wait(response, attempt)
                    except JiraError as exc:
                        retry_after = exc.retry_after
                raise JiraError(f"Jira returned HTTP {status}", status, retry_after)
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError
                return data
            except ValueError:
                error = UncertainWrite if write else JiraError
                raise error("Jira returned an unexpected JSON response", status) from None
        raise JiraError("Read attempts exhausted")

    def get(self, path: str, **params) -> dict[str, Any]:
        return self.request("GET", path, params=params)

    def pages(self, path: str, *, platform: bool = False, **params) -> list[dict]:
        results = []
        offset_key, limit_key = ("startAt", "maxResults") if platform else ("start", "limit")
        offset = 0
        for _ in range(1000):
            page = self.get(path, **params, **{offset_key: offset, limit_key: 50})
            values = page.get("values")
            if not isinstance(values, list):
                raise JiraError("Jira pagination response has no values list")
            results.extend(values)
            last = page.get("isLast" if platform else "isLastPage")
            if last is True or (
                platform and offset + len(values) >= page.get("total", float("inf"))
            ):
                return results
            if last is None:
                raise JiraError("Jira pagination metadata missing; discovery incomplete")
            if not values:
                if last is False:
                    raise JiraError("Jira returned an empty non-final page; discovery incomplete")
                return results
            offset += len(values)
        raise JiraError("Pagination safety limit reached; discovery incomplete")

    def identity(self) -> dict:
        user = self.get("/rest/api/3/myself")
        if not user.get("accountId") or user.get("active") is not True:
            raise SafetyError("Jira did not return an active authenticated identity")
        return user

    def target(self, key: str | None = None) -> tuple[dict, dict]:
        configured = self.settings.require_target()
        key = configured if key is None else key
        self.settings.assert_issue_key(key)
        issue = self.get(f"/rest/api/3/issue/{key}", fields="project,status")
        project = issue["fields"]["project"]
        if (
            issue.get("key") != key
            or project.get("key") != self.settings.jira_project_key
            or str(project.get("id")) != self.settings.jira_project_id
        ):
            raise SafetyError(
                "Actual Jira issue project does not match the configured test project"
            )
        if not str(issue.get("id", "")).isdigit():
            raise SafetyError("Jira returned no stable numeric issue ID")
        request = self.get(f"/rest/servicedeskapi/request/{issue['id']}")
        if (
            str(request.get("issueId")) != str(issue["id"])
            or request.get("issueKey") != key
            or str(request.get("serviceDeskId")) != self.settings.jira_service_desk_id
        ):
            raise SafetyError("JSM request does not match the designated issue and service desk")
        desk = self.get(f"/rest/servicedeskapi/servicedesk/{self.settings.jira_service_desk_id}")
        if (
            str(desk.get("projectId")) != self.settings.jira_project_id
            or desk.get("projectKey") != self.settings.jira_project_key
        ):
            raise SafetyError("Service desk does not belong to the configured project")
        return issue, request

    def permissions(self, issue_id: str) -> dict[str, bool]:
        keys = [
            "BROWSE_PROJECTS",
            "ADD_COMMENTS",
            "EDIT_ISSUES",
            "TRANSITION_ISSUES",
            "ASSIGN_ISSUES",
        ]
        data = self.get("/rest/api/3/mypermissions", issueId=issue_id, permissions=",".join(keys))
        return {
            key: data.get("permissions", {}).get(key, {}).get("havePermission") is True
            for key in keys
        }

    def post_probe_comment(self, issue_id: str, body: str, public: bool) -> dict:
        if self.settings.accessflow_dry_run:
            raise SafetyError("Dry-run mode forbids Jira writes")
        issue, _ = self.target()
        if str(issue["id"]) != issue_id:
            raise SafetyError("Comment target is outside the designated sandbox issue")
        permissions = self.permissions(issue_id)
        if not all(permissions[k] for k in ("BROWSE_PROJECTS", "ADD_COMMENTS")):
            raise SafetyError("Comment permissions changed; write blocked")
        return self.request(
            "POST",
            f"/rest/servicedeskapi/request/{issue_id}/comment",
            json={"body": body, "public": public},
        )

    def post_internal_triage_comment(self, key: str, issue_id: str, body: str) -> dict:
        if self.settings.accessflow_dry_run:
            raise SafetyError("Dry-run mode forbids Jira writes")
        issue, _ = self.target(key)
        if str(issue["id"]) != issue_id:
            raise SafetyError("Triage target changed; write blocked")
        permissions = self.permissions(issue_id)
        if not all(permissions[k] for k in ("BROWSE_PROJECTS", "ADD_COMMENTS")):
            raise SafetyError("Triage comment permissions are not confirmed")
        if not body.startswith("AccessFlow automated triage (v1)\n"):
            raise SafetyError("Unexpected triage comment format")
        return self.request(
            "POST",
            f"/rest/servicedeskapi/request/{issue_id}/comment",
            json={"body": body, "public": False},
        )
