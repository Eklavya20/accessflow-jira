"""Unattended authority is separate from historical per-comment approvals."""

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from accessflow.config import SafetyError


class WritePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    approved: bool = False
    site: str
    project: str
    service_desk_id: str
    request_type_ids: list[str]
    issue_keys: list[str] = Field(min_length=1, max_length=10)
    summary_prefix: str = Field(min_length=5)
    expires_at: datetime
    max_actions: int = Field(ge=1, le=10)
    max_actions_per_poll: int = Field(default=1, ge=1, le=1)
    public: bool = False
    operation: str = "internal_triage_comment"
    allowed_outcomes: list[str] = Field(min_length=1)


def approved_policy(settings):
    if not settings.accessflow_worker_write_enabled:
        raise SafetyError("Unattended writes are disabled")
    if settings.accessflow_dry_run:
        raise SafetyError("Global dry-run blocks unattended writes")
    try:
        raw = settings.accessflow_write_policy_path.read_bytes()
        policy = WritePolicy.model_validate_json(raw)
    except (OSError, ValueError):
        raise SafetyError("Invalid unattended write policy") from None
    fingerprint = hashlib.sha256(raw).hexdigest()
    if (
        not settings.accessflow_approved_policy_sha256
        or fingerprint != settings.accessflow_approved_policy_sha256
        or not policy.approved
        or policy.public
        or policy.operation != "internal_triage_comment"
        or policy.expires_at.tzinfo is None
        or policy.expires_at <= datetime.now(UTC)
        or policy.site != settings.jira_site_url
        or policy.project != settings.jira_project_key
        or policy.project not in settings.allowed_projects
        or policy.service_desk_id != settings.jira_service_desk_id
        or not set(policy.request_type_ids) <= settings.request_types
    ):
        raise SafetyError("Unattended policy approval, scope, or expiry does not match")
    return policy, fingerprint


def eligible_for_write(settings, result, request):
    policy, _ = approved_policy(settings)
    return (
        request.request_type_id in policy.request_type_ids
        and request.issue_key in policy.issue_keys
        and result.decision.outcome in policy.allowed_outcomes
        and result.request_type_id == request.request_type_id
        and result.issue_id == request.issue_id
        and request.summary.startswith(policy.summary_prefix)
    )


def authorize(settings, store, result, request):
    policy, fingerprint = approved_policy(settings)
    if not eligible_for_write(settings, result, request):
        raise SafetyError("Request is outside the unattended policy scope")
    store.reserve_write(fingerprint, result.operation_key, request.issue_id, policy.max_actions)
    return fingerprint
