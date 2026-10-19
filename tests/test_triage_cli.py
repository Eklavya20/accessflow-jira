import json

from accessflow import cli


def test_process_cli_defaults_to_dry_run(workflow, settings, monkeypatch, capsys):
    client, api = workflow
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "JiraClient", lambda _: client)
    assert cli.main(["process", "AFTEST-1"]) == 0
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["mode"] == "dry_run"
    assert result["decision"]["outcome"] == "ready_for_human_fulfillment"
    assert api.posts == 0


def test_local_show_and_audit_need_no_jira_connection(workflow, settings, monkeypatch, capsys):
    from accessflow.processor import process

    client, _ = workflow
    saved = process(client, "AFTEST-1")
    monkeypatch.setattr(cli, "Settings", lambda: settings)

    def forbidden(_):
        raise AssertionError("Local inspection must not construct a network client")

    monkeypatch.setattr(cli, "JiraClient", forbidden)
    assert cli.main(["show", "AFTEST-1"]) == 0
    assert json.loads(capsys.readouterr().out)["result_id"] == saved.result_id
    assert cli.main(["audit", "AFTEST-1"]) == 0
    assert json.loads(capsys.readouterr().out)[-1]["event"] == "request_classified"


def test_cli_write_without_hash_is_blocked(workflow, settings, monkeypatch, capsys):
    client, api = workflow
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "JiraClient", lambda _: client)
    assert cli.main(["process", "AFTEST-1", "--write"]) == 1
    assert "exact comment SHA-256" in capsys.readouterr().err
    assert api.posts == 0


def test_audit_limit_validation_has_no_jira_call(settings, monkeypatch, capsys):
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    assert cli.main(["audit", "AFTEST-1", "--limit", "0"]) == 1
    assert "Audit limit" in capsys.readouterr().err
