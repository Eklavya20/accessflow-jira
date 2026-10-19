"""One polling worker, local SQLite, and no implicit write authority."""

import json
import logging
import sqlite3
import time
import uuid
from threading import Event

from accessflow.config import SafetyError
from accessflow.domain import Policy, digest
from accessflow.ingestion import ingest
from accessflow.jira import JiraClient, JiraError
from accessflow.persistence import issue_lock, now
from accessflow.processor import process
from accessflow.worker_policy import approved_policy, authorize, eligible_for_write
from accessflow.worker_store import WorkerStore

log = logging.getLogger("accessflow.worker")


def discover_requests(client):
    settings = client.settings
    settings.require_target()
    found = {}
    for type_id in sorted(settings.request_types):
        rows = client.pages(
            "/rest/servicedeskapi/request",
            serviceDeskId=settings.jira_service_desk_id,
            requestTypeId=type_id,
            requestStatus="ALL_REQUESTS",
        )
        for row in rows:
            key, issue_id = row.get("issueKey", ""), str(row.get("issueId", ""))
            settings.assert_issue_key(key)
            if (
                not issue_id.isdigit()
                or str(row.get("serviceDeskId")) != settings.jira_service_desk_id
                or str(row.get("requestTypeId")) != type_id
            ):
                raise SafetyError("Discovery returned a request outside the configured scope")
            if issue_id in found and found[issue_id] != key:
                raise SafetyError("Inconsistent discovery identity")
            found[issue_id] = key
    return found


def source_fingerprint(request, policy):
    source = request.model_dump(exclude={"status", "request_type", "issue_key"})
    # Profile data is never persisted; reporter changes still invalidate source.
    source["requester_id"] = request.requester_id
    return digest({"source": source, "policy": policy.model_dump()})


class Worker:
    def __init__(self, settings, *, client_factory=JiraClient, clock=time.time, stop=None):
        self.settings, self.client_factory, self.clock = settings, client_factory, clock
        self.stop = stop if stop is not None else Event()
        self.run_id = uuid.uuid4().hex

    def runtime(self, **changes):
        with WorkerStore(self.settings.database_path()) as store:
            data = store.runtime(self.settings.jira_site_url)
            data.update(changes, heartbeat=self.clock(), run_id=self.run_id)
            store.save_runtime(self.settings.jira_site_url, data)
            return data

    def fail(self, store, issue_id, key, exc):
        settings, site = self.settings, self.settings.jira_site_url
        job = store.job(site, issue_id)
        attempts = job["attempts"] + 1
        transient = isinstance(exc, JiraError) and (
            exc.status is None or exc.status == 429 or exc.status >= 500
        )
        state = "retry" if transient and attempts < settings.accessflow_retry_attempts else "failed"
        delay = max(
            settings.accessflow_poll_seconds,
            min(3600, 60 * 2 ** (attempts - 1)),
            getattr(exc, "retry_after", 0),
        )
        reason = (
            str(exc) if isinstance(exc, (JiraError, SafetyError)) else "Local state/response error"
        )
        store.update_job(
            site,
            issue_id,
            state=state,
            attempts=attempts,
            retry_at=self.clock() + delay if state == "retry" else 0,
            error=reason,
        )
        store.audit(
            site, key, "worker_request_failed", state=state, reason=reason, attempts=attempts
        )
        self.runtime(last_error=reason, last_error_at=now())
        log.warning(
            json.dumps(
                {
                    "event": "worker_request_failed",
                    "issue_key": key,
                    "state": state,
                    "reason": reason,
                }
            )
        )

    def before_comment(self, client, store, request, result):
        policy_hash = authorize(self.settings, store, result, request)
        detail = client.get(
            "/rest/api/3/issue/" + result.issue_key, fields="status,assignee,project"
        )
        project = detail["fields"]["project"]
        if (
            str(detail.get("id")) != result.issue_id
            or detail.get("key") != result.issue_key
            or str(project.get("id")) != self.settings.jira_project_id
            or project.get("key") != self.settings.jira_project_key
        ):
            raise SafetyError("Pre-comment project/issue identity changed")
        store.audit(
            self.settings.jira_site_url,
            result.issue_key,
            "worker_before_comment",
            operation_key=result.operation_key,
            policy_hash=policy_hash,
            status_id=str(detail["fields"]["status"]["id"]),
            assignee_fingerprint=digest((detail["fields"].get("assignee") or {}).get("accountId")),
        )

    def poll(self, client):
        settings, site = self.settings, self.settings.jira_site_url
        self.runtime(state="polling", last_poll_started=now())
        with WorkerStore(settings.database_path()) as store:
            policy = Policy.load(settings.accessflow_policy_path)
            found = discover_requests(client)
            processed = skipped = failed = write_actions = 0
            for issue_id, key in found.items():
                if self.stop.is_set():
                    return
                self.runtime(state="polling")
                store.discover(site, issue_id, key)
                job = store.job(site, issue_id)
                if job["state"] == "failed" or job["retry_at"] > self.clock():
                    skipped += 1
                    continue
                try:
                    detail = client.get(f"/rest/api/3/issue/{key}", fields="updated,project")
                    if (
                        str(detail.get("id")) != issue_id
                        or detail.get("key") != key
                        or str(detail["fields"]["project"].get("id")) != settings.jira_project_id
                        or detail["fields"]["project"].get("key") != settings.jira_project_key
                    ):
                        raise SafetyError("Discovered issue project/identity did not verify")
                    updated = detail["fields"].get("updated", "")
                    policy_hash = digest(policy.model_dump())
                    execution = None
                    if settings.accessflow_worker_write_enabled:
                        active_policy, policy_fingerprint = approved_policy(settings)
                        if key in active_policy.issue_keys:
                            execution = digest([settings.accessflow_dry_run, policy_fingerprint])
                    # A policy change invalidates even an unchanged Jira timestamp.
                    cached = (
                        digest([updated, policy_hash, execution])
                        if execution
                        else digest([updated, policy_hash])
                    )
                    if (
                        job["state"] == "done"
                        and job["updated"] == cached
                        and self.clock() - job["checked_at"] < settings.accessflow_rescan_seconds
                    ):
                        skipped += 1
                        continue
                    request = ingest(client, key, policy)
                    if request.issue_id != issue_id:
                        raise SafetyError("Stable issue ID changed during worker ingestion")
                    if request.request_type_id not in settings.request_types:
                        store.update_job(
                            site, issue_id, state="ineligible", error="Request type changed"
                        )
                        continue
                    fingerprint = source_fingerprint(request, policy)
                    if execution:
                        fingerprint = digest([fingerprint, execution])
                    if job["state"] == "done" and job["source_hash"] == fingerprint:
                        store.update_job(
                            site,
                            issue_id,
                            updated=cached,
                            checked_at=self.clock(),
                            jira_updated_at=updated,
                        )
                        skipped += 1
                        continue
                    store.update_job(site, issue_id, state="running")
                    result = process(client, key)
                    if result.request_type_id != request.request_type_id:
                        raise SafetyError("Request type changed during worker processing")
                    if settings.accessflow_worker_write_enabled and eligible_for_write(
                        settings, result, request
                    ):
                        if write_actions >= 1:
                            store.update_job(
                                site,
                                issue_id,
                                state="retry",
                                retry_at=self.clock() + settings.accessflow_poll_seconds,
                            )
                            continue
                        authorization = authorize(settings, store, result, request)
                        store.audit(
                            site,
                            key,
                            "worker_write_authorized",
                            policy_hash=authorization,
                            operation_key=result.operation_key,
                        )
                        write_actions += 1
                        result = process(
                            client,
                            key,
                            write=True,
                            approved_sha256=result.comment_sha256,
                            retry=False,
                            before_post=lambda fresh, planned: self.before_comment(
                                client, store, fresh, planned
                            ),
                        )
                    store.update_job(
                        site,
                        issue_id,
                        updated=cached,
                        source_hash=fingerprint,
                        checked_at=self.clock(),
                        processed_at=now(),
                        state="done",
                        retry_at=0,
                        attempts=0,
                        error=None,
                        outcome=result.decision.outcome,
                        operation_key=result.operation_key,
                        comment_id=result.comment_id,
                        jira_updated_at=updated,
                    )
                    store.audit(
                        site,
                        key,
                        "worker_request_completed",
                        run_id=self.run_id,
                        outcome=result.decision.outcome,
                        result_id=result.result_id,
                        mode=result.mode,
                        comment_id=result.comment_id,
                    )
                    log.info(
                        json.dumps(
                            {
                                "event": "worker_request_completed",
                                "issue_key": key,
                                "outcome": result.decision.outcome,
                                "mode": result.mode,
                            }
                        )
                    )
                    processed += 1
                except (
                    JiraError,
                    SafetyError,
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    sqlite3.Error,
                ) as exc:
                    self.fail(store, issue_id, key, exc)
                    failed += 1
                    if getattr(exc, "status", None) in (401, 403, 429):
                        raise
            self.runtime(
                state="degraded" if failed else "waiting",
                last_successful_poll=now(),
                last_poll_summary={
                    "discovered": len(found),
                    "processed": processed,
                    "skipped": skipped,
                    "failed": failed,
                },
            )
            log.info(
                json.dumps(
                    {
                        "event": "poll_completed",
                        "discovered": len(found),
                        "processed": processed,
                        "skipped": skipped,
                        "failed": failed,
                    }
                )
            )

    def run(self):
        settings = self.settings
        settings.require_target()
        _ = settings.request_types
        with issue_lock(settings.database_path(), settings.jira_site_url, "polling-worker"):
            self.runtime(state="starting", started_at=now(), stopped_at=None)
            failures = self.runtime().get("consecutive_poll_failures", 0)
            try:
                with self.client_factory(settings) as client:

                    def request_guard(request):
                        if (
                            not settings.accessflow_worker_write_enabled
                            or settings.accessflow_dry_run
                        ) and request.method != "GET":
                            raise SafetyError("Read-only worker forbids every Jira mutation")

                    def response_log(response):
                        log.info(
                            json.dumps(
                                {
                                    "event": "jira_http",
                                    "method": response.request.method,
                                    "path": response.request.url.path,
                                    "status": response.status_code,
                                }
                            )
                        )

                    client.http.event_hooks["request"].append(request_guard)
                    client.http.event_hooks["response"].append(response_log)
                    while not self.stop.is_set():
                        state = self.runtime()
                        deadline = state.get("next_poll_at", 0)
                        if deadline > self.clock():
                            self.stop.wait(min(5, deadline - self.clock()))
                            continue
                        try:
                            self.poll(client)
                            failures = 0
                            self.runtime(consecutive_poll_failures=0)
                            delay = settings.accessflow_poll_seconds
                        except (
                            JiraError,
                            SafetyError,
                            OSError,
                            ValueError,
                            KeyError,
                            TypeError,
                            sqlite3.Error,
                        ) as exc:
                            failures += 1
                            reason = (
                                str(exc)
                                if isinstance(exc, (JiraError, SafetyError))
                                else "Local state/response error"
                            )
                            delay = max(
                                settings.accessflow_poll_seconds,
                                min(3600, 60 * 2 ** min(failures - 1, 6)),
                                getattr(exc, "retry_after", 0),
                            )
                            self.runtime(
                                state="degraded",
                                last_error=reason,
                                last_error_at=now(),
                                consecutive_poll_failures=failures,
                            )
                            log.warning(json.dumps({"event": "poll_failed", "reason": reason}))
                        self.runtime(next_poll_at=self.clock() + delay)
            finally:
                self.runtime(state="stopped", stopped_at=now())


def retry_job(settings, key):
    settings.assert_issue_key(key)
    with WorkerStore(settings.database_path()) as store:
        row = store.db.execute(
            "SELECT issue_id,state FROM worker_jobs WHERE site=? AND issue_key=?",
            (settings.jira_site_url, key),
        ).fetchone()
        if not row or row["state"] not in ("failed", "retry"):
            raise SafetyError("Only a failed/retry worker request may be scheduled")
        # Never alter triage_operations: uncertain effects still require reconciliation.
        store.update_job(
            settings.jira_site_url, row["issue_id"], state="retry", attempts=0, retry_at=0
        )
        store.audit(settings.jira_site_url, key, "worker_retry_scheduled")
    return {
        "issue_key": key,
        "state": "retry",
        "writes_enabled": settings.accessflow_worker_write_enabled,
    }
