import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from accessflow.config import SafetyError


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    applications: dict[str, list[str]]
    access_levels: dict[str, list[str]]
    privileged_levels: list[str]
    field_mapping: dict[Literal["application", "access_level", "justification"], str] = {}
    fulfillment_team: str = "IT support team"
    review_team: str = "Authorized application owner or security reviewer"

    @model_validator(mode="after")
    def validate_catalogue(self):
        for catalog in (self.applications, self.access_levels):
            seen = {}
            if not catalog:
                raise ValueError("Catalogues must not be empty")
            for canonical, aliases in catalog.items():
                if not canonical.strip():
                    raise ValueError("Empty catalogue entry")
                for value in [canonical, *aliases]:
                    normalized = value.strip().casefold()
                    if not normalized or (normalized in seen and seen[normalized] != canonical):
                        raise ValueError("Empty or conflicting catalogue alias")
                    seen[normalized] = canonical
        if not self.privileged_levels or not set(self.privileged_levels) <= set(self.access_levels):
            raise ValueError("Privileged levels must reference supported access levels")
        if len(set(self.field_mapping.values())) != len(self.field_mapping):
            raise ValueError("Each mapped field must have one meaning")
        return self

    def canonical(self, value: str | None, category: str) -> str | None:
        if not value:
            return None
        catalog = self.applications if category == "application" else self.access_levels
        for canonical, aliases in catalog.items():
            if value.strip().casefold() in {v.strip().casefold() for v in [canonical, *aliases]}:
                return canonical
        return None

    @classmethod
    def load(cls, path):
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise SafetyError(
                "Policy file is missing or invalid; inspect catalogue configuration"
            ) from None


class RequestInput(BaseModel):
    issue_id: str
    issue_key: str
    request_type_id: str
    request_type: str
    status: str
    summary: str
    description: str
    mapped_fields: dict[str, str] = {}
    requester_id: str | None = Field(default=None, exclude=True, repr=False)
    requester_updates: list[str] = []


class Decision(BaseModel):
    application: str | None = None
    access_level: str | None = None
    justification: str | None = None
    missing: list[str] = []
    uncertainties: list[str] = []
    privileged: bool = False
    outcome: Literal[
        "ready_for_human_fulfillment", "needs_information", "privileged_review", "manual_triage"
    ]
    reason: str
    action: str


class ProcessingResult(BaseModel):
    result_id: int
    issue_id: str
    issue_key: str
    request_type_id: str
    request_type: str
    current_status: str
    requester_available: bool
    revision: int
    decision: Decision
    operation_key: str
    proposed_comment: str
    comment_sha256: str
    mode: Literal["dry_run", "write"]
    write_status: str
    comment_id: str | None = None
