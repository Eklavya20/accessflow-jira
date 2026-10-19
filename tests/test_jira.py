from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from accessflow.config import SafetyError
from accessflow.jira import JiraClient, JiraError, UncertainWrite


@pytest.mark.parametrize("status", [401, 403, 404, 302])
def test_no_retry_permanent_errors_or_redirects(settings, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            headers={"Location": "https://evil.invalid"},
            json={"detail": "secret response body"},
        )

    with JiraClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(JiraError, match=f"HTTP {status}") as error:
            client.identity()
    assert len(calls) == 1
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_reads_retry_and_recover(settings, status):
    attempts, waits = [], []

    def handler(request):
        attempts.append(request)
        return (
            httpx.Response(status, headers={"Retry-After": "2"}, json={})
            if len(attempts) < 3
            else httpx.Response(200, json={"ok": True})
        )

    with JiraClient(settings, transport=httpx.MockTransport(handler), sleep=waits.append) as client:
        assert client.get("/rest/api/3/myself") == {"ok": True}
    assert len(attempts) == 3
    assert waits == [2, 2]


def test_timeout_retry_exhaustion(settings):
    attempts = []

    def handler(request):
        attempts.append(request)
        raise httpx.ConnectTimeout("secret detail", request=request)

    with JiraClient(
        settings, transport=httpx.MockTransport(handler), sleep=lambda _: None
    ) as client:
        with pytest.raises(JiraError, match="bounded read attempts"):
            client.identity()
    assert len(attempts) == settings.jira_read_attempts


def test_respects_long_retry_after_without_early_retry(settings):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"}, json={})

    with JiraClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(JiraError, match="exceeds local wait budget"):
            client.identity()
    assert len(calls) == 1


def test_http_date_retry_after(client):
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=10))
    wait = client.retry_wait(httpx.Response(429, headers={"Retry-After": future}), 0)
    assert 8 < wait <= 10


def test_platform_and_jsm_pagination(settings):
    calls = []

    def handler(request):
        calls.append(request)
        platform = request.url.path.endswith("search")
        offset = int(request.url.params["startAt" if platform else "start"])
        return httpx.Response(
            200,
            json={
                "values": [{"id": str(offset)}],
                "isLast" if platform else "isLastPage": offset == 1,
            },
        )

    with JiraClient(settings, transport=httpx.MockTransport(handler)) as client:
        assert len(client.pages("/rest/api/3/project/search", platform=True)) == 2
        assert len(client.pages("/rest/servicedeskapi/servicedesk")) == 2
    assert len(calls) == 4


def test_nonfinal_empty_page_is_not_reported_complete(settings):
    with JiraClient(
        settings,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"values": [], "isLastPage": False})
        ),
    ) as client:
        with pytest.raises(JiraError, match="empty non-final"):
            client.pages("/rest/servicedeskapi/servicedesk")


@pytest.mark.parametrize("platform", [False, True])
def test_empty_page_without_completion_metadata_is_not_success(settings, platform):
    with JiraClient(
        settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"values": []}))
    ) as client:
        with pytest.raises(JiraError, match="pagination metadata missing"):
            client.pages("/rest/servicedeskapi/servicedesk", platform=platform)


def test_empty_platform_page_with_zero_total_is_complete(settings):
    with JiraClient(
        settings,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"values": [], "total": 0})
        ),
    ) as client:
        assert client.pages("/rest/api/3/project/search", platform=True) == []


def test_no_absolute_remote_paths(client):
    with pytest.raises(SafetyError):
        client.get("https://evil.invalid/rest/api/3/myself")


def test_dry_run_client_refuses_post(client):
    with pytest.raises(SafetyError, match="Dry-run"):
        client.post_probe_comment("9001", "body", False)


def test_dry_run_also_guards_low_level_transport(client):
    with pytest.raises(SafetyError, match="Dry-run"):
        client.request("POST", "/rest/servicedeskapi/request/9001/comment", json={})


def test_scoped_client_preserves_gateway_prefix_and_basic_auth(settings):
    settings.jira_token_kind = "scoped"
    settings.jira_cloud_id = "12345678-1234-1234-1234-123456789abc"
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"accountId": "test", "active": True})

    with JiraClient(settings, transport=httpx.MockTransport(handler)) as client:
        client.identity()
    assert str(calls[0].url) == settings.api_base + "/rest/api/3/myself"
    assert calls[0].headers["Authorization"].startswith("Basic ")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_posts_are_never_automatically_retried(settings, status):
    settings.accessflow_dry_run = False
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={})

    with JiraClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UncertainWrite):
            client.request("POST", "/rest/servicedeskapi/request/9001/comment", json={})
    assert len(calls) == 1
