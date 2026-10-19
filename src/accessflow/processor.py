import hashlib

from accessflow.config import SafetyError
from accessflow.domain import Policy, ProcessingResult, digest
from accessflow.ingestion import ingest
from accessflow.jira import JiraClient, JiraError, UncertainWrite
from accessflow.parsing import classify
from accessflow.persistence import Store, issue_lock

OUTCOMES = {
    "ready_for_human_fulfillment": "Ready for human fulfillment",
    "needs_information": "Missing information",
    "privileged_review": "Privileged access - human review required",
    "manual_triage": "Manual triage required",
}


def semantic(request, decision, policy):
    return digest(
        {
            "format": "triage-v1",
            "request_type_id": request.request_type_id,
            "decision": decision.model_dump(),
            "policy": policy.model_dump(),
        }
    )


def comment_body(decision, operation_key: str) -> str:
    return "\n".join(
        [
            "AccessFlow automated triage (v1)",
            "Application: " + (decision.application or "Not provided"),
            "Access level: " + (decision.access_level or "Not provided"),
            "Business justification: " + (decision.justification or "Not provided"),
            "Outcome: " + OUTCOMES[decision.outcome],
            "Reason: " + decision.reason,
            "Missing information: " + (", ".join(decision.missing) or "None"),
            "Action: " + decision.action,
            "This records triage only. Human authorization and fulfillment remain required.",
            f"[accessflow-triage:v1:{operation_key}]",
        ]
    )


def verify_remote(client, issue_id, comment_id, body, author_id):
    if not comment_id or not str(comment_id).isdigit():
        raise SafetyError("Invalid triage comment ID; reconcile before retry")
    remote = client.get(f"/rest/servicedeskapi/request/{issue_id}/comment/{comment_id}")
    if (
        str(remote.get("id")) != str(comment_id)
        or remote.get("body") != body
        or remote.get("public") is not False
        or remote.get("author", {}).get("accountId") != author_id
    ):
        raise SafetyError("Triage comment body, author, or internal visibility did not verify")


def write_back(client, store, result, request, policy, *, retry: bool, before_post=None):
    site, key, operation_key = client.settings.jira_site_url, result.issue_key, result.operation_key
    operation = store.operation(operation_key)
    current_actor = client.identity()["accountId"]
    author = operation["author_id"] or current_actor
    if operation["comment_id"]:
        verify_remote(
            client, result.issue_id, operation["comment_id"], result.proposed_comment, author
        )
        store.state(operation_key, "verified")
        result.comment_id, result.write_status = operation["comment_id"], "already_verified"
        store.audit(site, key, "comment_already_verified", comment_id=result.comment_id)
        return
    comments = client.pages(f"/rest/servicedeskapi/request/{result.issue_id}/comment")
    # Resolve older uncertain effects before allowing a newer classification to post.
    older = store.db.execute(
        "SELECT * FROM triage_operations WHERE site=? AND issue_id=? "
        "AND operation_key<>? AND state IN ('pending','uncertain')",
        (site, result.issue_id, operation_key),
    ).fetchall()
    for old in older:
        old_marker = f"[accessflow-triage:v1:{old['operation_key']}]"
        old_matches = [c for c in comments if old_marker in c.get("body", "")]
        old_id = old["comment_id"] or (str(old_matches[0]["id"]) if len(old_matches) == 1 else None)
        if not old_id or len(old_matches) > 1:
            raise SafetyError(
                "An earlier request revision has an uncertain write; reconcile it first"
            )
        verify_remote(
            client, result.issue_id, old_id, old["body"], old["author_id"] or current_actor
        )
        store.state(old["operation_key"], "verified", comment_id=old_id)
        store.audit(site, key, "older_comment_reconciled", comment_id=old_id)
    marker = f"[accessflow-triage:v1:{operation_key}]"
    matching = [c for c in comments if marker in c.get("body", "")]
    if len(matching) > 1:
        raise SafetyError("Multiple matching triage markers; manual reconciliation required")
    if matching:
        comment_id = str(matching[0]["id"])
        verify_remote(client, result.issue_id, comment_id, result.proposed_comment, author)
        store.state(operation_key, "verified", comment_id=comment_id, author_id=author)
        result.comment_id, result.write_status = comment_id, "reconciled"
        store.audit(site, key, "comment_reconciled", comment_id=comment_id)
        return
    if operation["state"] in ("pending", "uncertain"):
        raise SafetyError(
            "Remote outcome remains uncertain; no POST retried. Inspect Jira and audit."
        )
    if operation["state"] == "blocked" and not retry:
        raise SafetyError("Prior write was denied; fix permission/configuration then use retry")
    # Reject changed input before the POST rather than apply a stale approval.
    refreshed = ingest(client, key, policy)
    if semantic(refreshed, classify(refreshed, policy), policy) != semantic(
        request, result.decision, policy
    ):
        raise SafetyError(
            "Request changed after planning; dry-run again and approve the new comment"
        )
    permissions = client.permissions(result.issue_id)
    if not all(permissions[k] for k in ("BROWSE_PROJECTS", "ADD_COMMENTS")):
        store.state(operation_key, "blocked", error="Comment permissions not confirmed")
        raise SafetyError("Browse Projects and Add Comments are required for write-back")
    if before_post is not None:
        before_post(refreshed, result)
    store.state(operation_key, "pending", author_id=current_actor)
    store.audit(
        site,
        key,
        "comment_post_intent",
        operation_key=operation_key,
        comment_sha256=result.comment_sha256,
        public=False,
    )
    try:
        created = client.post_internal_triage_comment(key, result.issue_id, result.proposed_comment)
        comment_id = str(created.get("id", ""))
        if not comment_id.isdigit():
            raise UncertainWrite("Write response has no comment ID; reconcile before retry")
        store.state(operation_key, "pending", comment_id=comment_id)
        verify_remote(client, result.issue_id, comment_id, result.proposed_comment, current_actor)
        store.state(operation_key, "verified", comment_id=comment_id)
        result.comment_id, result.write_status = comment_id, "created_and_verified"
        store.audit(site, key, "comment_created_and_verified", comment_id=comment_id)
    except (JiraError, SafetyError) as exc:
        # A definitive permission/validation rejection can be retried explicitly.
        # Other post/verification failures remain uncertain and must reconcile.
        state = (
            "blocked"
            if isinstance(exc, JiraError) and exc.status in (400, 401, 403)
            else "uncertain"
        )
        store.state(operation_key, state, error=str(exc))
        raise


def process(
    client: JiraClient,
    key: str,
    *,
    write: bool = False,
    approved_sha256: str | None = None,
    retry: bool = False,
    before_post=None,
) -> ProcessingResult:
    settings = client.settings
    settings.assert_issue_key(key)
    policy = Policy.load(settings.accessflow_policy_path)
    site, database = settings.jira_site_url, settings.database_path()
    with Store(database) as store:
        try:
            issue, _ = client.target(key)
        except (JiraError, SafetyError) as exc:
            store.audit(site, key, "ingestion_failed", reason=str(exc))
            raise
        with issue_lock(database, site, str(issue["id"])):
            result = None
            try:
                request = ingest(client, key, policy)
                if request.issue_id != str(issue["id"]):
                    raise SafetyError("Issue identity changed before the processing lock")
                decision = classify(request, policy)
                semantic_hash = semantic(request, decision, policy)
                revision = store.revision(site, request.issue_id, key, semantic_hash)
                operation_key = digest(
                    [site, request.issue_id, "triage-v1", revision, semantic_hash]
                )
                body = comment_body(decision, operation_key)
                operation = store.plan(site, key, request.issue_id, revision, operation_key, body)
                result = ProcessingResult(
                    result_id=0,
                    issue_id=request.issue_id,
                    issue_key=key,
                    request_type_id=request.request_type_id,
                    request_type=request.request_type,
                    current_status=request.status,
                    requester_available=bool(request.requester_id),
                    revision=revision,
                    decision=decision,
                    operation_key=operation_key,
                    proposed_comment=body,
                    comment_sha256=hashlib.sha256(body.encode()).hexdigest(),
                    mode="write" if write else "dry_run",
                    write_status=operation["state"],
                    comment_id=operation["comment_id"],
                )
                store.save_result(site, digest(request.model_dump()), result)
                store.audit(
                    site,
                    key,
                    "request_classified",
                    result_id=result.result_id,
                    outcome=decision.outcome,
                    revision=revision,
                    mode=result.mode,
                )
                if not write:
                    return result
                if approved_sha256 != result.comment_sha256:
                    raise SafetyError(
                        "Write requires explicit approval of the exact comment SHA-256"
                    )
                store.audit(site, key, "write_authorized", comment_sha256=result.comment_sha256)
                previous_dry_run = settings.accessflow_dry_run
                try:
                    settings.accessflow_dry_run = False
                    write_back(
                        client, store, result, request, policy, retry=retry, before_post=before_post
                    )
                finally:
                    settings.accessflow_dry_run = previous_dry_run
                store.update_result(result)
                return result
            except (JiraError, SafetyError) as exc:
                if result:
                    operation = store.operation(result.operation_key)
                    result.write_status = operation["state"]
                    result.comment_id = operation["comment_id"]
                    store.update_result(result)
                store.audit(
                    site,
                    key,
                    "processing_failed",
                    reason=str(exc),
                    operation_key=result.operation_key if result else None,
                )
                raise
