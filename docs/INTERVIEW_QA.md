# AccessFlow interview Q&A

Use these as short answers, then offer the code/evidence for more detail. Scope is the delivered sandbox service; no prospective adopter's architecture is assumed.

## What problem did you choose to solve?

Preparing an access request requires repeated checks for application, permission level and justification, followed by a suitable human next action. I automated that preparation and its traceability, while keeping authorization and fulfillment with humans. The business hypothesis is less repetitive triage; no organizational workload baseline or measured saving exists yet.

## What did you actually deliver?

A real JSM integration, deterministic four-outcome rules, a polling worker, SQLite checkpoints/action journal/audit, and authenticated local operational controls. AIS-4 proved automatic dry-run discovery. After separate bounded approval, AIS-5 automatically received internal comment 10007; independent reads verified it, and a later poll/real worker restart created no duplicate. Writes are disabled again.

## Why Python rather than only native Jira Automation?

For simple Jira-local rules, I would evaluate native automation first: Atlassian provides triggers, actions and audit logs, with less service-hosting responsibility. Python let this project make rule tests, explicit action intentions, reconciliation and operating boundaries visible in code. It also provides a potential foundation for cross-system work, but that is future scope and brings maintenance cost. I am not claiming native automation cannot integrate systems or prevent loops. The actual subscription/entitlement has not been confirmed. [Native triggers](https://support.atlassian.com/cloud-automation/docs/jira-automation-triggers/), [audit logs](https://support.atlassian.com/cloud-automation/docs/what-is-the-automation-audit-log/), [service limits](https://support.atlassian.com/cloud-automation/docs/automation-service-limits/).

## Why polling, one worker and SQLite?

They met the small sandbox requirement without public ingress or another infrastructure dependency. Polling defaults to 60 seconds; source rescans catch requester comments even if Jira's update timestamp does not change. SQLite and OS-owned locks coordinate one host using the same journal. The worker scans every visible eligible request page, so high-volume efficiency, multiple hosts and a different database need a separate design/measurement decision.

## How do discovery and changed-request detection work?

The JSM request-list API is paginated and filtered by service desk/request type; actual issue project/desk IDs are checked before processing. Update timestamps support cheap skips, with periodic full ingestion and a fingerprint of relevant fields, requester corrections and policy. Internal/self-generated comments and status-only changes do not create business revisions. Visibility is limited to the configured identity's permissions; five visible sandbox requests do not prove organization-wide coverage. [JSM request API](https://developer.atlassian.com/cloud/jira/service-desk/rest/api-group-request/).

## How do you prevent duplicates? Is it exactly once?

No distributed exactly-once guarantee is claimed. A stable issue ID, semantic revision and decision/policy hash identify an operation; an OS lock excludes concurrent processing on the same host/journal. Before a remote attempt, the application commits its pending intent and policy reservation. A stored comment ID or paginated marker search is verified against exact body, author and internal visibility. An uncertain operation with no visible match is held for investigation, not blindly resent. This deliberately trades some automatic progress for avoiding a second effect.

## What if the request changes back to an earlier value?

Semantic changes increment a revision, including A→B→A, so current work does not silently rely on an outdated comment. A new CLI effect needs a newly approved exact body hash. The worker's consumed one-action policy permits one revision per allowed issue; it is not a general authorization to keep commenting on changes. Relevant updates/reversions are offline-tested; no live edit experiment is claimed.

## How do retries and rate limits work?

GETs have bounded transient retries with backoff and Retry-After handling. Long server delays become persisted scheduling deadlines rather than early retries, including across restart. Worker jobs have a default five-attempt bound; discovery failures use a capped backoff and remain observable. HTTP 401/403 are not retried inside one transport attempt. POST uncertainty is reconciled, not automatically resent. Fault scenarios are tested offline; a live outage was not induced.

## What happens after a crash or a denied write?

The committed intention survives a crash; restart checks remote evidence before any new effect. If a crash occurred before the POST but after the pending reservation, absence of a comment cannot prove that no delayed write exists, so the operation can remain blocked for human investigation. A definitive denied write requires repair and deliberate authorized retry. An administrative retry schedules eligible failed work without deleting intentions, resetting budgets or forcing a POST. Native graceful restart and persistence were verified; live crash/outage and full deployment restore remain untested.

## What are the permission boundaries?

Jira account permissions and token scopes determine what the identity can access; code/policy authorization further restrict what AccessFlow may do. The worker verifies allowlisted project/desk/type, requires approved policy bytes and hash, enabled flags, matching target/outcome/summary, expiry and a durable budget. It can only append an internal triage comment and read it back. The scoped token is not itself proof of least privilege: earlier Jira permission discovery reported capabilities broader than the application uses. Production identity/scopes need review. The policy hash detects changes; it is not a signed human-approval service.

## How are secrets and the admin API protected?

Jira secrets remain in private local configuration, not source/CLI arguments or reports; a separate random Bearer token protects detail/control routes with constant-time comparison. Native binding is loopback, with only aggregate health unauthenticated. Real Git ignore checks cover the requested secret/state/log paths, and source scans did not find the current tokens. There is no project Git repository or history here to certify; ignore rules do not erase prior commits elsewhere. Local `.env`/SQLite files are not claimed encrypted, and there is no enterprise SSO, RBAC or TLS deployment yet.

## How do you disable writes, and what is the current state?

Currently worker-write enabled is false, global dry-run is true, policy approved is false and the configured activation hash is blank. The service has been restarted with those settings; its healthy worker continues read-only polling. A policy-file disable is checked before new POSTs; changing environment flags requires restart. An in-flight request cannot be recalled. The AIS-5 reservation remains consumed. Future write scope needs fresh explicit approval.

## Why does AIS-5's latest local result say dry-run while Jira has a comment?

The authorized write result and audit are retained, with verified remote comment ID 10007. Returning the service to dry-run caused one local reevaluation of its changed execution configuration, reusing that verified operation/comment. The latest result's mode describes that local run, not whether an earlier write happened. Show the historical `comment_created_and_verified` audit plus independent Jira evidence.

## What did the final review change?

It fixed health readiness inheriting a successful poll from a previous run, corrected health mode when global dry-run wins, and made empty pagination without completion metadata fail closed. It also added ignore coverage for common SQLite extensions/journals and logs outside the standard directories. The original 177 tests remain; nine new regression cases bring the suite to 186. No parser/business rule, database schema, dependency or Jira effect was added for the interview.

## What does the evidence prove, and what does it not prove?

It proves five synthetic requests were classified, four approved triage comments plus a separate connectivity comment were observed, and one of those triage comments was produced automatically under separate policy authority. Offline tests exercise all four outcomes and failure/concurrency cases. Native startup, health, admin auth, persistence and graceful restart were exercised live. Docker/Compose, host reboot supervision, production load, live outage/crash recovery, full restore and organizational adoption are unverified. The audit is application history, not a tamper-proof compliance ledger.

## What would you integrate next, if the product case justified it?

First establish the authoritative application catalogue, reviewer ownership and measurable pilot need. Possible later integrations are a maintained catalogue/CMDB, authoritative human approval evidence, or an identity platform through a separately authorized provisioner. Each needs API/schema validation, least privilege, duplicate/failure design and its own acceptance evidence. Current “ready for human fulfillment” is never permission to provision. Webhook/indexed discovery, supervised deployment and CI quality checks are engineering opportunities, not delivered features.

## What would you ask a technical product owner?

Which preparation step is costly enough to automate, and how would we establish a baseline? What evidence would make native automation sufficient? Who owns catalogue decisions, failed work and ongoing hosting cost? Which operational/security gates must pass before a pilot expands? These questions keep delivery tied to a validated user outcome rather than an expanding integration backlog.
