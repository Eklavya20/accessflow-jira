import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SafetyError(Exception):
    """An operator must resolve configuration or an uncertain write outcome."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    jira_site_url: str
    jira_email: str = Field(min_length=3, repr=False)
    jira_api_token: SecretStr = Field(repr=False)
    jira_token_kind: Literal["scoped", "unscoped"] = "scoped"
    jira_cloud_id: str = ""
    jira_project_key: str = ""
    jira_project_id: str = ""
    jira_service_desk_id: str = ""
    jira_allowed_project_keys: str = ""
    jira_test_issue_key: str = ""
    accessflow_dry_run: bool = True
    accessflow_probe_comment_body: str = Field(default="", max_length=2000)
    jira_query_approvals: bool = False
    accessflow_policy_path: Path = Path("config/policy.json")
    database_url: str = "sqlite:///data/accessflow.db"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    jira_timeout_seconds: float = Field(default=20, gt=0, le=120)
    jira_read_attempts: int = Field(default=3, ge=1, le=5)
    jira_max_retry_wait_seconds: float = Field(default=30, ge=0, le=120)
    accessflow_poll_seconds: int = Field(default=60, ge=30, le=86400)
    accessflow_rescan_seconds: int = Field(default=300, ge=60, le=86400)
    accessflow_request_type_ids: str = ""
    accessflow_retry_attempts: int = Field(default=5, ge=1, le=10)
    accessflow_admin_token: SecretStr = Field(default=SecretStr(""), repr=False)
    accessflow_worker_write_enabled: bool = False
    accessflow_write_policy_path: Path = Path("config/worker-write-policy.json")
    accessflow_approved_policy_sha256: str = ""
    accessflow_bind_host: Literal["127.0.0.1", "0.0.0.0"] = "127.0.0.1"
    accessflow_port: int = Field(default=8765, ge=1024, le=65535)

    @property
    def request_types(self) -> set[str]:
        values = {v.strip() for v in self.accessflow_request_type_ids.split(",") if v.strip()}
        if not values or not all(re.fullmatch(r"[1-9][0-9]*", v) for v in values):
            raise SafetyError("Configure explicit numeric ACCESSFLOW_REQUEST_TYPE_IDS")
        return values

    @field_validator("jira_site_url")
    @classmethod
    def cloud_site(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.atlassian\.net", parsed.netloc)
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use an HTTPS Atlassian Cloud site origin")
        return value.rstrip("/")

    @field_validator("jira_api_token")
    @classmethod
    def nonempty_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("API token is required")
        return value

    @field_validator("jira_project_key")
    @classmethod
    def project_key(cls, value: str) -> str:
        if value and not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            raise ValueError("Invalid project key")
        return value

    @field_validator("jira_project_id", "jira_service_desk_id")
    @classmethod
    def numeric_id(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Use a numeric Jira ID")
        return value

    @model_validator(mode="after")
    def validate_cloud_id(self) -> "Settings":
        if self.jira_token_kind == "scoped":
            self.jira_cloud_id = str(UUID(self.jira_cloud_id))
        return self

    @property
    def api_base(self) -> str:
        if self.jira_token_kind == "scoped":
            return f"https://api.atlassian.com/ex/jira/{self.jira_cloud_id}"
        return self.jira_site_url

    @property
    def allowed_projects(self) -> set[str]:
        return {key.strip() for key in self.jira_allowed_project_keys.split(",") if key.strip()}

    def require_target(self) -> str:
        if not all(
            (
                self.jira_project_key,
                self.jira_project_id,
                self.jira_service_desk_id,
                self.jira_test_issue_key,
            )
        ):
            raise SafetyError("Set project key/ID, service desk ID, and designated test issue key")
        self.assert_issue_key(self.jira_test_issue_key)
        return self.jira_test_issue_key

    def assert_issue_key(self, key: str) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*", key):
            raise SafetyError("A canonical issue key is required")
        if key.rsplit("-", 1)[0] != self.jira_project_key:
            raise SafetyError("Issue key is outside the configured test project")
        if self.jira_project_key not in self.allowed_projects:
            raise SafetyError("Configured test project is absent from the project allowlist")

    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix) or self.database_url == prefix:
            raise SafetyError("The feasibility journal requires a file-backed sqlite:/// URL")
        value = self.database_url[len(prefix) :]
        if value == ":memory:":
            raise SafetyError("A durable database is required")
        return Path(value)
