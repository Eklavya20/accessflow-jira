import httpx
import pytest

from accessflow.config import SafetyError
from accessflow.jira import JiraClient
from scripts import verify_milestone2 as verification


@pytest.fixture
def guarded(settings, monkeypatch):
    sent = []

    def server(request):
        sent.append(request)
        return httpx.Response(201, json={"id": "1"})

    monkeypatch.setattr(
        verification,
        "JiraClient",
        lambda value: JiraClient(value, transport=httpx.MockTransport(server)),
    )
    proposal = {
        "issue_key": "AIS-1",
        "issue_id": "10006",
        "proposed_comment": "Exact approved body",
    }
    trace, context, budgets = [], {"phase": "initial_write"}, {"10006": 1}
    with verification.guarded_client(
        settings, {"AIS-1": proposal}, trace, context, budgets
    ) as client:
        yield client, sent, context


def test_verifier_permits_one_exact_internal_post_only(guarded):
    client, sent, _ = guarded
    client.http.post(
        "rest/servicedeskapi/request/10006/comment",
        json={"body": "Exact approved body", "public": False},
    )
    with pytest.raises(SafetyError):
        client.http.post(
            "rest/servicedeskapi/request/10006/comment",
            json={"body": "Exact approved body", "public": False},
        )
    assert len(sent) == 1


@pytest.mark.parametrize(
    "method,path,body",
    [
        (
            "POST",
            "rest/servicedeskapi/request/10006/comment",
            {"body": "Changed body", "public": False},
        ),
        (
            "POST",
            "rest/servicedeskapi/request/10006/comment",
            {"body": "Exact approved body", "public": True},
        ),
        (
            "POST",
            "rest/servicedeskapi/request/10007/comment",
            {"body": "Exact approved body", "public": False},
        ),
        ("POST", "rest/api/3/issue/AIS-1/transitions", {"transition": {"id": "1"}}),
        ("PUT", "rest/api/3/issue/AIS-1", {"fields": {"assignee": {"accountId": "other"}}}),
        ("POST", "rest/servicedeskapi/request/10006/approval/1", {"decision": "approve"}),
        ("DELETE", "rest/servicedeskapi/request/10006/comment/1", {}),
    ],
)
def test_verifier_blocks_all_out_of_scope_writes_before_transport(guarded, method, path, body):
    client, sent, _ = guarded
    with pytest.raises(SafetyError):
        client.http.request(method, path, json=body)
    assert not sent


@pytest.mark.parametrize(
    "phase", ["preflight", "same_process_repeat", "fresh_process_repeat", "final_read_back"]
)
def test_repeat_verification_cannot_create_any_comment(guarded, phase):
    client, sent, context = guarded
    context["phase"] = phase
    with pytest.raises(SafetyError):
        client.http.post(
            "rest/servicedeskapi/request/10006/comment",
            json={"body": "Exact approved body", "public": False},
        )
    assert not sent
