import re

from accessflow.domain import Decision, Policy, RequestInput

LABELS = {
    "application": "Application",
    "access_level": "Access level",
    "justification": "Business justification",
}


def plain_text(value) -> str:
    """Extract text from Jira ADF without evaluating HTML or other input."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(plain_text(child) for child in value)
    if isinstance(value, dict):
        suffix = "\n" if value.get("type") in ("paragraph", "heading", "hardBreak") else ""
        return str(value.get("text", "")) + plain_text(value.get("content", [])) + suffix
    return ""


def formatted_values(text: str) -> dict[str, list[str]]:
    return {
        field: [
            m.strip()
            for m in re.findall(rf"(?im)^\s*(?:[-*]\s*)?{label}\s*:[ \t]*([^\r\n]*)", text)
            if m.strip()
        ]
        for field, label in LABELS.items()
    }


def classify(request: RequestInput, policy: Policy) -> Decision:
    candidates = formatted_values(request.description)
    for field, value in request.mapped_fields.items():
        if value.strip():
            candidates[field].append(value.strip())
    # Only formatted updates from the actual requester can replace original values.
    # Ingestion excludes internal/automation comments and other participants.
    for update in request.requester_updates:
        for field, values in formatted_values(update).items():
            if values:
                candidates[field] = values
    values = {}
    uncertainties = []
    for field, raw_values in candidates.items():
        normalized = {}
        for value in raw_values:
            canonical = (
                policy.canonical(value, field)
                if field in ("application", "access_level")
                else value
            )
            normalized[(canonical or value).casefold()] = canonical or value
        if len(normalized) > 1:
            uncertainties.append(f"Conflicting {LABELS[field].lower()} values")
            values[field] = None
        else:
            values[field] = next(iter(normalized.values()), None)
    if not candidates["application"]:
        # A single catalogue application can be identified in a simple free-text
        # request. Permissions and justification are never guessed from prose.
        text = request.summary + "\n" + request.description
        matches = {
            name
            for name, aliases in policy.applications.items()
            if any(
                re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.I)
                for alias in [name, *aliases]
            )
        }
        if len(matches) == 1:
            values["application"] = matches.pop()
        elif len(matches) > 1:
            uncertainties.append("Multiple catalogue applications mentioned")
        else:
            uncertainties.append("Application cannot be determined from the configured catalogue")
    if values["application"] and not policy.canonical(values["application"], "application"):
        uncertainties.append("Application is outside the configured catalogue")
    if values["access_level"] and not policy.canonical(values["access_level"], "access_level"):
        uncertainties.append("Access level is outside the configured catalogue")
    for field, value in values.items():
        if value and len(value) > (600 if field == "justification" else 120):
            uncertainties.append(f"{LABELS[field]} exceeds the supported review length")
            values[field] = value[: 600 if field == "justification" else 120]
    missing = [LABELS[k] for k, value in values.items() if not value]
    prose = (
        request.summary + "\n" + request.description + "\n" + "\n".join(request.requester_updates)
    )
    prose = re.sub(r"(?im)^\s*(?:[-*]\s*)?Access level\s*:[^\r\n]*", "", prose)
    privileged_mention = any(
        re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", prose, re.I)
        for level in policy.privileged_levels
        for alias in [level, *policy.access_levels[level]]
    )
    privileged = (
        values["access_level"] in policy.privileged_levels
        or privileged_mention
        or any(
            policy.canonical(value, "access_level") in policy.privileged_levels
            for value in candidates["access_level"]
        )
    )
    if (
        privileged_mention
        and values["access_level"]
        and values["access_level"] not in policy.privileged_levels
    ):
        uncertainties.append("Privileged access mentioned; access level needs human confirmation")
    if uncertainties:
        outcome, reason = "manual_triage", "; ".join(uncertainties)
        action = "IT support team to clarify the uncertain details before fulfillment."
    elif missing:
        outcome, reason = "needs_information", "Missing: " + ", ".join(missing)
        action = "IT support team to ask the requester for: " + ", ".join(missing) + "."
        if privileged:
            action += " Privileged access also requires authorized human review."
    elif privileged:
        outcome, reason = "privileged_review", "Privileged access requires explicit human review"
        action = policy.review_team + " to review authorization before any fulfillment."
    else:
        outcome, reason = "ready_for_human_fulfillment", "Required information present"
        action = policy.fulfillment_team + " to review and fulfill under the normal access policy."
    return Decision(
        **values,
        missing=missing,
        uncertainties=uncertainties,
        privileged=privileged,
        outcome=outcome,
        reason=reason,
        action=action,
    )
