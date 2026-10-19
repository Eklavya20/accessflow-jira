import pytest
from pydantic import ValidationError

from accessflow.cli import main
from accessflow.config import SafetyError, Settings


@pytest.mark.parametrize(
    "url",
    [
        "http://sandbox.atlassian.net",
        "https://sandbox.atlassian.net.evil.invalid",
        "https://user:secret@sandbox.atlassian.net",
        "https://sandbox.atlassian.net/path",
        "https://sandbox.atlassian.net?token=secret",
        "https://localhost",
    ],
)
def test_reject_unsafe_site(settings, url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**settings.model_dump(), "jira_site_url": url})


def test_scoped_gateway(settings):
    value = Settings(
        _env_file=None,
        **{
            **settings.model_dump(),
            "jira_token_kind": "scoped",
            "jira_cloud_id": "12345678-1234-1234-1234-123456789abc",
        },
    )
    assert value.api_base == (
        "https://api.atlassian.com/ex/jira/12345678-1234-1234-1234-123456789abc"
    )


def test_scoped_requires_cloud_id(settings):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**settings.model_dump(), "jira_token_kind": "scoped"})


def test_config_repr_hides_secrets(settings):
    assert "unit-test-token" not in repr(settings)
    assert settings.jira_email not in repr(settings)


@pytest.mark.parametrize("key", ["OTHER-1", "AFTEST-1/../../OTHER-1", "9001", "AFTEST-0"])
def test_target_key_validation(settings, key):
    with pytest.raises(SafetyError):
        settings.assert_issue_key(key)


def test_empty_allowlist_fails_closed(settings):
    settings.jira_allowed_project_keys = ""
    with pytest.raises(SafetyError):
        settings.require_target()


def test_missing_config_cli_is_actionable_and_redacted(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    for key in ("JIRA_SITE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_CLOUD_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JIRA_API_TOKEN", "do-not-print-this")
    assert main(["discover"]) == 2
    output = capsys.readouterr()
    assert "configuration_invalid" in output.err
    assert "do-not-print-this" not in output.err
    assert not output.out
