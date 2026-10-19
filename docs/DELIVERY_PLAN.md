# Delivery plan and implementation checklist

This is a gated plan, not a promise of completed live acceptance by that date. Scope will follow observed Jira capabilities.

## Milestone 1 — Jira feasibility (passed: connectivity and controlled write)

- [x] Inspect repository: initially empty; no Jira environment variables or `.env` found.
- [x] Review official Cloud REST documentation and record API/plan uncertainties.
- [x] Select smallest architecture and define MVP boundaries.
- [x] Create safe typed configuration and `.env.example`.
- [x] Implement real HTTP client, bounded GET retries, and pagination.
- [x] Implement project/desk/type/required-field discovery.
- [x] Implement designated request/project validation and permission/capability checks.
- [x] Implement explicit comment preview, durable reservation, read-back, and reconciliation.
- [x] Run offline tests and CLI startup/configuration checks; record measured results.
- [x] User configures a JSM Cloud sandbox, scoped token, and synthetic test request.
- [x] Protect local token files, discover Cloud ID, and populate ignored scoped-token configuration.
- [x] Verify live Platform API read of AIS-1, its expected description/status, and effective permissions.
- [x] Discover live AIS service desk, Request admin access type, required fields, and transitions.
- [x] User supplies a replacement v2 token; identity and JSM request reads now pass.
- [x] Authenticate against live Jira and discover actual configuration.
- [x] Read the designated real request and validate effective permissions.
- [x] User explicitly approved the exact proposed INTERNAL comment on AIS-1; no repeat approval required for that operation.
- [x] Write the exact internal comment and verify it by a separate GET: comment 10003.
- [x] Repeat in the same process and a new interpreter; one matching comment remains and no duplicate POST occurs.

Gate passed with real read/write evidence in `reports/milestone1-live.json` and [RESULTS.md](RESULTS.md). Account plan/native approval entitlement is not inferred from connectivity. This does not establish a functional MVP or deployment.

## Milestone 2 — Functional CLI workflow (passed live acceptance)

- [x] Use the verified comment endpoint for human next-action summaries; defer richer routing/approvals.
- [x] Map request identity/type, description/ADF and requester availability to typed input.
- [x] Extract application/access level/justification deterministically; flag unknown/conflicting data.
- [x] Configure application/access catalogues, privileged levels, and human team wording.
- [x] Implement all four outcomes, versioned internal comment proposals, and durable result history.
- [x] Require exact current comment-hash authorization for new internal triage writes.
- [x] Reevaluate field edits and formatted public corrections from the requester.
- [x] Add safe repeat/retry/reconciliation, local audit/show, per-issue locks and crash recovery tests.
- [x] Pass original and new offline tests and a real AIS-1 privileged dry-run.
- [x] User manually created AIS-2 (standard) and AIS-3 (incomplete).
- [x] Read/classify all three real cases and present the exact resulting comments/hashes.
- [x] Obtain explicit approval for the three exact internal triage comments and hashes.
- [x] Verify live write/read-back: AIS-1 comment 10004, AIS-2 comment 10005, AIS-3 comment 10006; all internal.
- [x] Reprocess all three in the same process and a fresh interpreter: same IDs, one match per ticket, no POSTs.
- [x] Inspect durable verified state and CLI show/audit after restart; preserve status, assignment and M1 comment.

Gate passed for the agreed internal-comment CLI workflow. All three real cases have approved write/read-back and persistent repeat/restart evidence; all four outcomes and failure/concurrency behavior pass offline. No provisioning, public comments, status/assignment edits, or automated approval decisions are included. Full unattended operation and production rollout are separate gates.

## Milestone 3 — Run independently (passed with native Windows fallback)

The user's Milestone 3 brief expands this milestone to include the polling/API/native deployment work previously planned for Milestone 4. Milestones 1 and 2 remain passed.

- [x] Phase A: scoped JSM request discovery, pagination/deduplication, update/source fingerprints and automatic dry-run classification.
- [x] Phase A: SQLite worker/job status, audit, retry scheduling, Retry-After deadlines and single-worker lock.
- [x] Phase B: live existing-request poll (50 GETs, 0 writes, 3 classifications).
- [x] Phase B: user-created AIS-4 discovered automatically; GitHub Read-only classified ready for human fulfillment without manual processing.
- [x] Phase B: subsequent poll skipped all four unchanged requests; AIS-4 retained one result and no comment.
- [x] Phase C: authenticated FastAPI status/result/audit/retry/shutdown and real worker health; public health only, loopback default.
- [x] Phase C: hidden detached native Windows start/stop/restart tested; AIS-4 state survived with no redundant processing.
- [x] Phase C: Dockerfile/Compose, persistent volume, build-context secret exclusion, non-root runtime and health/restart settings prepared.
- [ ] Phase C Docker runtime: unavailable on this host; native fallback verified instead. Linux image/volume migration still needs validation.
- [x] Phase D: concrete bounded AIS-5-only internal-comment policy and exact example presented for separate approval.
- [x] Phase D: user explicitly approved the exact bounded policy hash; activated only its one-action AIS-5 scope.
- [x] Phase E: user created AIS-5 after activation; worker automatically posted internal comment 10007; independent read-back, later poll and real worker restart passed with no duplicates.
- [x] Phase F current: offline regressions, measured results, runbook and two-minute business/architecture demo updated.
- [x] Phase F final: recorded passed live evidence; disabled all unattended write gates and restarted a healthy read-only worker; updated final milestone verdict and demo.

Gate passed for all eight conditions in the current brief, using its permitted native Windows fallback. Separately authorized automatic internal write-back, independent read-back, duplicate prevention, SQLite/native restart persistence and final write disablement are verified. The one-action approval is consumed. Docker runtime and broader production hardening remain outstanding; no old approval was reused.

Interview-readiness review: corrected inherited health readiness, health mode reporting and malformed empty-page completion; expanded state/log ignore patterns. All original 177 tests remain, with nine regressions added (186 passing). Native read-only restart and existing Jira comment read-back were revalidated without new mutations. Product, business analysis, architecture, Q&A, demo and final evidence are indexed in the [interview pack](INTERVIEW_PACK.md).

### Reliability retained and expanded

- [x] Durable issue/results/action-intent and append-only application audit tables; triage schema version checked.
- [x] OS-owned per-issue locking on one local host; cross-process exclusion and release tested.
- [x] Input/decision revisions and comment-specific duplicate prevention.
- [x] Reconcile uncertain comments before retrying; block unresolved outcomes and older uncertain revisions.
- [x] Durable per-request retry scheduling and persisted discovery/rate-limit deadlines; worker schema upgrade tested.
- [x] Consistent SQLite backup reopened with matching journal counts and integrity check.
- [ ] Full deployment migration/restore drill.
- [ ] Any future field/transition effect needs its own reconciliation and separate permission/authorization.
- [x] Bounded per-request transient retries, rate-limit scheduling, persistent failure visibility.
- [x] Offline tests cover restart, concurrency, comment updates, denied access, timeouts and 429/5xx.
- [x] Verify live comment duplicate prevention and CLI-process restart using persisted state.
- [x] Actual native automatic-worker restart with AIS-4 state preserved.
- [ ] Controlled live outage/crash recovery drill.

Live fault injection and full deployment recovery have not been performed. A second developer's failure/audit review remains useful before broader rollout.

## Milestone 4 — Broader operational hardening (partly delivered by revised Milestone 3)

- [x] FastAPI health plus authenticated outcomes, failure/retry, audit and shutdown endpoints.
- [x] Polling worker with durable scheduling and overlap/reconciliation strategy.
- [x] Request-type/project filters and separately gated bounded write capability; one AIS-5 action was explicitly approved, consumed and disabled. Future actions need new authorization.
- [ ] Confirm actual plan, named human reviewers and operating ownership before broader rollout; do not infer native approvals.
- [x] Dockerfile/Compose with persistent SQLite volume and restart policy, local binding only (runtime untested).
- [ ] Database migration, backup/restore, secret rotation, and retention procedures.
- [x] Native service continues after its launcher exits, independently of editor/terminal; VS Code itself was not closed.
- [ ] Test the intended final deployment/runtime, boot supervision and sustained host availability.
- [ ] Run full live acceptance and measure results; finalize runbook/demo.

Gate: repeatable deployment, all agreed live acceptance criteria, explicit remaining risks. Do not publish a public service.

## Milestone 5 — Optional extraction enhancement (deferred)

- [ ] Only consider after deterministic live acceptance passes.
- [ ] Compare structured LLM extraction with the baseline on synthetic labeled cases.
- [ ] Deterministic authorization policy, robust fallback, confidence/review behavior, measured value.

## Dependencies and validation checkpoints

Account owner provides sandbox access and confirms plan; agent identity/token permits reads and the approved comment. IT owner validates catalog, sensitive levels, reviewers, clarification wording, and queue filters. Developer validates recovery/audit evidence. Product owner reviews scope and actual outcomes before claiming business impact.

Risks: token/permission blockers (diagnose with discovery, never bypass), restricted workflows (use supported human routing), ambiguous requests (ask or escalate), uncertain writes (reconcile), deadline pressure (show truthful partial delivery), local workstation downtime (persistent state plus explicit host/session availability requirements). A Windows host still needs to remain powered on for local automation.
