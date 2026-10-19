# Operational runbook

Applies to the CLI, native Windows background worker and local authenticated API. Native autonomous discovery, approved internal write/read-back, later-poll and real worker-restart acceptance passed. Docker/Compose is supplied but runtime-untested because Docker was unavailable. The historical one-action AIS-5 policy is consumed and disabled. Check health to establish current runtime status; acceptance evidence does not imply a service is running in a fresh clone. Future unattended writes require new bounded authorization.

## Start, observe, restart and stop

Run from the repository root with the installed virtual environment. Follow [Jira setup](JIRA_SETUP.md) to configure explicit `ACCESSFLOW_REQUEST_TYPE_IDS` for your own service desk, a poll interval (default 60 seconds), and a private random admin token of at least 32 characters. The acceptance sandbox used request types `9,10`; those IDs are not portable. Preserve an existing private `.env` and do not print it. `ACCESSFLOW_DRY_RUN=true` and `ACCESSFLOW_WORKER_WRITE_ENABLED=false` remain the safe defaults.

```powershell
.\.venv\Scripts\python.exe scripts/manage_service.py start
.\.venv\Scripts\python.exe scripts/manage_service.py health
.\.venv\Scripts\python.exe scripts/manage_service.py status
Get-Content reports/native-service.stderr.log -Tail 40
.\.venv\Scripts\python.exe scripts/manage_service.py stop
.\.venv\Scripts\python.exe scripts/manage_service.py start
```

The hidden detached process uses the repository as its working directory and survives the launcher exiting. No open editor/terminal is required. The machine must stay powered on and the user session available; reboot/logon autostart and Windows Service installation are not provided or claimed. `serve` runs in the foreground when needed. Do not use Uvicorn reload or multiple workers. `worker-once` is for deliberate diagnostics when no service worker is running; it is not used for the AIS-4 automatic acceptance test.

`http://127.0.0.1:8765/health` returns 503 while starting, stopped, stale or degraded, and 200 only when the current worker is alive, heartbeating and has completed a successful poll. A fresh process may wait for the persisted poll/rate-limit deadline. Job failures are separately visible in authenticated status. Credentials and issue details never belong in a health URL.

Final interview review re-ran native stop/start, observed startup 503 followed by 200 / dry_run, and confirmed unchanged source/operation/comment state for all five tickets. Readiness now explicitly rejects a successful poll inherited from an earlier process. The current listener was verified on 127.0.0.1:8765. See [final verification](FINAL_VERIFICATION.md); these commands do not establish reboot supervision or live crash/outage recovery.

| Route | Authentication / operation |
| --- | --- |
| `GET /health` | Unauthenticated aggregate worker readiness |
| `GET /admin/status` | Bearer token; runtime, last poll/error, counts, jobs and operation states |
| `GET /admin/issues/AIS-4` | Bearer token; persisted result and planned comment |
| `GET /admin/issues/AIS-4/audit?limit=100` | Bearer token; durable audit, limit 1–1000 |
| `POST /admin/issues/AIS-4/retry` | Bearer token; schedules only failed/retry jobs, rejects completed work |
| `POST /admin/shutdown` | Bearer token; signals worker/service stop |

`manage_service.py` reads the admin credential privately from settings. For API clients, put it in an Authorization Bearer header, never in a query string. These are local operations endpoints, not a public website. Detailed CLI equivalents are `worker-status`, `worker-retry ISSUE`, `show ISSUE`, and `audit ISSUE`.

Stop waits for graceful completion and checks that the API closes. The service waits up to 30 seconds for its worker thread during shutdown; an operation exceeding that window may require journal reconciliation after restart. Durable pending intents remain intact. No force-kill/reset is part of the normal stop procedure. A dead worker requests service exit; native detached mode has no automatic process supervisor, whereas Compose has a restart policy.

## Docker Compose (not runtime-verified here)

With Docker/Compose installed, use `docker compose up -d --build`, `docker compose logs -f accessflow`, `docker compose restart accessflow`, and `docker compose down`. The port is bound to host `127.0.0.1:8765`, SQLite lives in `accessflow-data`, runtime secrets come from `.env`, and the image runs as UID 10001. `.dockerignore` uses an allowlist so token files, `.env`, state, logs and attachments are excluded from builds. Container config is read-only mounted from `config/` so policy disablement reaches a running service. Do not use `down -v` to clear duplicate-prevention state.

Native SQLite and the Docker volume are distinct locations. Before changing deployment, stop the source worker, make a consistent SQLite backup, place it in the destination volume with the proper owner, then verify integrity and journal records before starting one worker. Do not run parallel native/container instances against different journals. Volume migration, Linux image startup, restart and reboot behavior still need actual Docker validation. Container health failure alone does not trigger Docker restart; process exit does.

## Worker failures and safe retry

`worker_jobs` records failed/retry state, error, attempts and next retry time. A cycle can classify healthy requests while a request-specific transient error schedules recovery. Authentication failures and 429 stop further requests in that cycle. Retry-After is honored across restarts; a long delay is not shortened to fit the local wait budget. Per-job retries stop after five attempts by default. Discovery failure retains the prior successful poll and schedules another bounded-backoff scan.

After correcting a failure, use `worker-retry AIS-KEY` or the authenticated retry endpoint. It schedules work for a later normal poll, does not directly POST to Jira, does not reset action budgets, and cannot clear uncertainty from `triage_operations`. Terminal permission-denied write operations still require deliberate exact-comment CLI retry authorization after repair; scheduling the worker is not a force resend. Keep every journal/table and the lock directory intact.

New/changed source is reevaluated on discovery; unchanged update timestamps skip expensive reads until the periodic 300-second source rescan. That rescan catches relevant requester replies even without a changed Jira timestamp. Unknown/malformed source goes to human triage. Own/internal comments and status-only changes do not produce a new business revision. Large queues require performance validation; current discovery scans every visible eligible request page.

## Unattended write enablement and emergency disable

Follow [the bounded policy record](MILESTONE3_WRITE_POLICY.md). The public policy is a disabled, expired example. The acceptance environment retains its exact disabled sandbox policy at ignored `data/worker-write-policy.local.json`, selected privately in `.env`. Changing a policy file changes its approval hash; no historical approval applies to the public example or a new deployment. Historical M1/M2 approvals never enable worker writes. Only a separately approved exact policy hash, enabled worker flag and global dry-run false can permit a matched internal comment. The AIS-5 test consumed its one-action budget; current policy approved=false, worker enabled=false, global dry-run=true and approved hash blank. The service was restarted with those settings and independently reverified. Preserve the reservation and journals; future actions need a new review/approval. Requests outside approved scope remain classifications without writes. No status, assignment, approval or permission action is implemented.

To stop future writes immediately, edit the policy selected by `ACCESSFLOW_WRITE_POLICY_PATH` to `approved: false` (or `config/worker-write-policy.json` if unset), or stop the service using the authenticated shutdown command. A policy check runs again just before each new POST. Then set worker-write enabled false and dry-run true in private `.env` and restart if read-only polling should continue. An in-flight POST cannot be recalled. Rollback means stop, retain evidence and account-owner review; automatic comment deletion is not authorized.

## Routine use

Run from the repository so the intended `.env` and relative database path are selected. Use `discover` for inventory and `check` for designated request/permission checks. Keep dry-run enabled unless performing the explicitly approved probe. `probe-comment` requires exact `--confirm` and explicit `--visibility`.

Reports are JSON on stdout; lifecycle/error events are JSON on stderr. Do not share raw request or credential data. Discovery itself is read-only and does not save full audit history. Triage saves structured results, proposed comment bodies and action/audit records locally; they can contain confidential request details. Keep the ignored database/reports private and establish retention before rollout.

## Triage operation

Run `python -m accessflow process ISSUE-KEY --dry-run` using the virtual environment from the repository root. It persists a result and exact proposed internal comment but sends no Jira writes. Inspect `show ISSUE-KEY` and `audit ISSUE-KEY --limit 100` without contacting Jira. Review the exact proposed comment and SHA-256. Only with explicit authorization run `process ISSUE-KEY --write --approve-comment-sha256 HASH`.

The write flag is scoped to that command and overrides dry-run in memory only after exact-hash validation. It never changes `.env`. The CLI cannot send public triage comments, transition statuses, assign tickets, decide approvals, or provision access. The missing-information outcome produces an internal instruction for IT; contacting the requester remains a human step.

`retry ISSUE-KEY` defaults to a new dry-run. `retry ISSUE-KEY --write --approve-comment-sha256 HASH` can retry a definitive 400/401/403 rejection after correction and exact approval. It does not force a pending/uncertain write. Inspect audit history to distinguish blocked permission/configuration failures from uncertainty.

For pending/uncertain effects, an authorized write run first reads the saved comment ID or scans every JSM comment page for the versioned marker. It verifies exact body, internal visibility and original author before marking the effect verified. If no comment is visible, the operation remains blocked from resending, even if the process may have crashed before its POST. Keep state intact and investigate; no force/reset command exists. A deleted/edited/wrong-visibility comment needs operator review rather than reposting.

If request content/policy changes, dry-run creates a new semantic revision and new approval hash. It does not repeat a comment merely because Jira's status changed or AccessFlow added its own comment. Older uncertain revisions must reconcile before a newer one can write. Formatted public replies from the actual requester can correct details; other participants and internal comments cannot supply those corrections.

Per-issue OS file locks use the stable site/issue ID. A concurrent attempt reports that the issue is busy; retry after it completes. Locks release on process exit and do not expire while network calls are in progress. Use one local database/lock directory on one host; do not run independent copies or place these files on a network share. Keep lock files in place rather than deleting them to override an active process.

## Catalogue configuration

`ACCESSFLOW_POLICY_PATH` defaults to `config/policy.json`. Maintain the finite catalogue, access aliases, privileged levels and human team instructions there. The file version is included in action fingerprints. `field_mapping` optionally maps `application`, `access_level`, or `justification` to discovered request field IDs with text/ADF values. Arbitrary select-list/user/option schemas are not automatically interpreted. Prefer the documented labeled description until mappings are validated against actual requests.

The parser uses single-line English labels. It can identify one catalogue application in simple prose, but it never guesses an access level or business justification. Multiple/conflicting/unknown values go to manual triage. Privileged prose is treated conservatively, including conflict with a standard access level. The small catalogue is not an exhaustive enterprise entitlement policy.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Exit 2 / configuration invalid | Check named fields in `.env`, working directory, and overriding environment variables. Never print all settings to diagnose. Scoped tokens need a valid cloud UUID. |
| HTTP 401 | Check token owner email, token kind, expiry/revocation, correct site/cloud ID. Stop writes; do not retry invalid credentials repeatedly. |
| HTTP 403 | Check token scopes, project permissions, JSM agent access, and organization restrictions with the admin. Do not infer a plan limit solely from this status. |
| HTTP 404 | Confirm issue is an accessible JSM portal request and IDs belong to the same project/desk. Hidden resources can also appear unavailable. |
| No request types | Set test project allowlist, confirm service desk ID and agent access, rerun discovery. |
| No approvals | Confirm actual workflow with admin; an empty list is inconclusive. Use documented human review if native approvals are unavailable. |
| 429 / long Retry-After | Wait at least the server-specified interval before rerunning reads. A pending POST requires reconciliation, not a new write. |
| 5xx / transport timeout | Reads retry within configured bounds; after exhaustion investigate connectivity and retry later. Pending write outcomes must be reconciled. |
| Internal comment denied | Verify agent role and Add Comments. Keep internal visibility; public requires separate explicit authorization. |
| Database busy/local error | Check local file permissions, available disk, and competing processes. Keep the SQLite journal intact. |
| Pytest temp access failure | Run `.\.venv\Scripts\python.exe scripts/check.py` for a workspace-local temp root. |

## Uncertain or failed connectivity comments

Retain the database and stop concurrent probe runs. Rerun the same command with the same configured ticket, visibility, identity, and site. It checks an existing comment ID or scans all JSM comment pages for the exact stable marker and author, then verifies the body and visibility with a separate GET. It never automatically resends an existing pending operation without a visible comment.

If the result remains uncertain, inspect Jira with an authorized agent and the account owner. A crash before sending can leave a pending reservation with no remote comment. There is intentionally no automatic reset/force-resend command. Do not delete journal rows or switch database/site/identity to force another POST. Resolve the evidence with the developer before any new write. A wrong-visibility or removed comment is a blocker, not a reason to post another.

## SQLite initialization and backup

The first non-dry-run probe creates the parent directory and `connectivity_probes` table using `CREATE TABLE IF NOT EXISTS`, with WAL and full synchronous mode. No separate database setup is required. It contains no token or request body; it binds the comment text using a SHA-256 hash. Keep it on a local disk, not a shared network filesystem. Stop probe processes before a backup; use SQLite's backup API for a consistent copy including any WAL contents. Do not copy only the main DB while a writer is running.

Journal schema revision 2 adds `body_sha256` to the original table when absent. Legacy rows can resume only with the original marked comment text; a text change blocks without posting. The legacy-column upgrade has an offline regression test. Back up state before upgrading; do not manually alter tables. The processor/worker schemas below add current version checks and audit/job storage; enterprise migration lifecycle and full deployment restore remain rollout gates. The probe journal alone does not establish worker recovery.

Milestone 2 adds `triage_schema` version 1 and separate `triage_issues`, `triage_results`, `triage_operations`, and `triage_audit` tables in the same database. Milestone 3 adds `worker_schema` version 2, `worker_jobs`, `worker_runtime` and `worker_write_budget`; its additive v1→v2 upgrade preserves jobs and adds the Jira update timestamp. Unsupported versions are rejected. Stop the old service before upgrading, retain a consistent full backup, and preserve both original journals and worker tables. Scheduled-worker recovery is implemented and offline-tested; the native AIS-4 restart passed live. An enterprise migration lifecycle and deployment restore still need validation.

## Credential rotation and cleanup

Revoke/rotate the token in Atlassian, update `.env` locally, and rerun read-only checks. Preserve the site/issue/journal identity for reconciliation. Keep synthetic test artifacts until evidence is reviewed; delete only with account-owner direction. No real employee access has been granted by this utility.

## Planned service operations

The native API/worker and control commands above exist. Run `scripts/manage_service.py backup` for a consistent SQLite backup saved to ignored `data/backup-*.db`; it uses SQLite's backup API and checks integrity. To restore, stop the service, preserve the current database and any WAL files, restore a validated backup to a fresh local path, configure `DATABASE_URL` for that path, verify integrity plus operation IDs, and start only one worker. Opening a backup and matching journal row counts has been tested; replacing a deployment database and Docker-volume restoration have not.

Before production adoption: assign operational/failure ownership, configure retention, validate token rotation/revocation and least privilege, test real outage/crash recovery and expected queue volume, test deployment/migrations/restore end to end, and install an appropriate supervisor. No production-readiness claim follows from the sandbox demonstration.
