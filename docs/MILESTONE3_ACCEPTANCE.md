# Milestone 3 live acceptance

Status: **Milestone 3 passes using the verified native Windows fallback.** AIS-4 passed autonomous dry-run; AIS-5 passed separately approved automatic internal write/read-back, later-poll and actual worker-restart checks. All unattended-write gates are disabled and the healthy worker remains dry-run. Neither request was manually processed; AIS-4 received no comment.

## Phase A — implemented and verified

The worker uses the existing JSM request-list API, filtered to AIS desk 2 and request types 9/10. The first guarded real poll made 50 GETs, classified AIS-1/2/3 and issued zero writes. Pagination, new/changed requests, source fingerprints, periodic rescans, own-comment loops, retries, deadlines, locking, persistence and admin controls have isolated offline tests. See [actual results](RESULTS.md).

## Phases B/C — real autonomous dry-run (passed)

1. Start the native service using `scripts/manage_service.py start`; keep dry-run true and worker writes false. Observe actual worker health rather than HTTP-server liveness alone.
2. User manually creates a Get IT help request with this input:

```text
Summary: TEST - AccessFlow M3 automatic discovery

Application: GitHub
Access level: Read-only
Business justification: Verifying independent AccessFlow polling in the sandbox.

Sandbox test only. No actual access should be granted.
```

3. User supplied AIS-4. Observe completion through worker logs, authenticated status and SQLite; do not process it manually. Expected outcome: `ready_for_human_fulfillment`.
4. Confirm `worker_request_completed`, dry-run mode, durable source hash, one processing result and no remote comment ID. Actual completion: October 19, 2026, 22:02:35 Europe/Paris.
5. Observe another complete poll: actual discovered 4 / processed 0 / skipped 4 / failed 0. Result count stays one.
6. Stop/start the native service, confirm a new worker run ID, healthy API and the same result ID, source hash, processing timestamp and result count. All passed.
7. Verify unauthenticated admin rejection (401) and completed-job retry rejection (409). Confirm local backup opens with SQLite integrity `ok` and matching journal counts.

Evidence is in ignored `reports/milestone3-AIS-4-first-and-repeat.json`, `reports/milestone3-native.json`, worker logs and SQLite. The detached process continued after the launcher exited; VS Code itself was not closed. Docker is not available on this machine, so no container/startup/restart result is claimed.

## Phases D/E — separately authorized automatic write (passed)

The user explicitly approved [the concrete bounded policy](MILESTONE3_WRITE_POLICY.md) and its exact activation hash. GET-only preflight confirmed AIS-5 absent. After activation, the user manually created AIS-5 and the worker automatically discovered issue 10010, classified GitHub Read-only as `ready_for_human_fulfillment`, and posted internal comment 10007 at 22:26:49 Europe/Paris. No CLI process/retry command was used. Independent GETs verified exact body, author, public=false and one marker match; pre-comment status/assignment and AIS-1 through AIS-4 snapshots were unchanged.

The next scheduled poll skipped all five unchanged requests. A fresh native service/worker run recovered the same verified operation/comment and also skipped all five. Both added zero POSTs; the entire worker mutation trace contains exactly one comment POST, HTTP 201. SQLite retained one consumed policy-budget reservation. A backup reopens with integrity ok and the same verified comment/budget.

After verification, the service was stopped, policy approved=false / worker enabled=false / dry-run=true / approved hash blank were restored, and the service was restarted read-only. Health returned 200 / dry_run, and a final independent GET still found one exact internal comment. Disabling execution mode caused one automatic local dry-run reevaluation, with no new Jira effect. Future actions need revised review and explicit approval. Never clear state or change database/site identity to force another action.

## Definition of done

| Condition from the user brief | Verified evidence |
| --- | --- |
| Discover a new real request automatically | AIS-4 dry-run and AIS-5 approved write, via worker polling |
| Classify without manual CLI processing | Correct GitHub Read-only outcome; worker logs and audit |
| Persist through restart | Same SQLite verified operation/comment after a fresh worker run |
| Prevent duplicate effects | One comment, zero additional POSTs in subsequent poll/restart |
| Test actual startup | Native hidden detached Windows service start/stop/restart |
| Observability and safe controls | Healthy worker endpoint, authenticated status/audit, rejected unauthenticated admin and completed-job retry |
| Separately approve and verify automatic write | Exact approved bounded policy, comment 10007 independently read back internal |
| Accurate documentation | Results, architecture, runbook, delivery plan and demo updated with runtime limits |

## Remaining evidence and interpretation

All eight scoped conditions pass with the user-permitted native fallback. Offline fixtures remain separate from live evidence. Live API-outage/crash injection, Linux/Compose execution, host reboot and full deployment restore are untested. Broad production readiness and measured labor savings are not established. The consumed one-action approval authorizes no future unattended write.
