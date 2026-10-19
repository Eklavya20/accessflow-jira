# Final interview verification report

Reviewed October 19, 2026 against the sandbox acceptance evidence. **The project is ready for a demonstration of verified sandbox execution and product trade-offs.** Milestones 1–3 passed within their stated scope using the native Windows fallback. This report does not establish production readiness or measured business benefit.

## 1. Implemented functionality

| Capability | Current implementation |
| --- | --- |
| Real Jira integration | Scoped-token HTTPS client, actual project/desk validation, paginated JSM discovery and comment reads |
| Automatic triage | One polling worker, default 60 seconds; deterministic application/access/justification rules; four typed outcomes |
| Change tracking | Jira timestamp checkpoint plus relevant source/policy fingerprint and periodic comment/source rescan |
| Durable processing | SQLite results, revisions, job state, retry deadlines, action intentions, comment IDs and audit history |
| Restricted effects | Exact-hash CLI write gate or separately approved bounded worker policy; worker writes only internal triage comments |
| Recovery/duplicates | Shared-journal OS locks, intent-before-effect, marker/body/author/visibility verification and conservative uncertainty reconciliation |
| Operations | Local authenticated FastAPI status/result/audit/retry/shutdown; aggregate worker health; native detached startup and logs |

Current write gates: worker enabled **false**, global dry-run **true**, policy approved **false**, configured activation hash **blank**. The consumed AIS-5 budget remains in SQLite. No new Jira mutation was permitted during interview preparation.

## 2. Offline-tested behavior

| Check | Actual result |
| --- | --- |
| Regression suite | **186 passed, 0 failed, 0 skipped**; original 177 cases retained, nine review regressions added |
| New review coverage | Previous-run health success, missing/invalid/naive readiness timestamps, dry-run precedence, malformed empty pagination and valid platform zero-total page |
| Existing coverage | Four outcomes, extraction/ADF/requester corrections, scope and permission denial, pagination, retries/rate limits, updates/self-comment loops, locks, persistence, uncertainty/crash scenarios, policy budgets and API authentication |
| Lint/format | Ruff passed; all 36 Python files passed formatting checks |
| Dependencies | `pip check` passed; one existing Starlette/AnyIO deprecation warning, no test failures |
| Published-source reproducibility | October 20 source-only export installed locked dependencies and the package in a fresh local environment; all 186 tests and checks passed. Initial release `4146c23` also passed [hosted Windows/Python 3.11 CI](https://github.com/Eklavya20/accessflow-jira/actions/runs/39332809467); logs independently verified |
| Credential scan | No current Jira/admin token, account-email or encoded Basic credential match in 67 reviewed source/config/documentation/build files; scanned values were not recorded |
| Git ignore engine | 21 private path cases ignored; five intended public paths retained, including `.env.example` |

At this review, ignore behavior was tested with real Git in an isolated ignored scratch repository; no project repository existed yet. Subsequent publication preparation initialized a local repository and audited its actual staged files; see [publication verification](PUBLICATION.md). Neither check certifies other copies, prior remote commits or deliberate force-adds. SQLite/log files and `.env` are not made encrypted by ignoring them.

Offline HTTP fixtures do not prove live API behavior. Dependency consistency is not a CVE scan, security certification or penetration test. The JUnit suite time was 8.45 seconds; it is not live throughput or a business-performance measure.

## 3. Live Jira-verified behavior

| Existing request | Verified result |
| --- | --- |
| AIS-1 | Privileged review; approved internal triage comment 10004; separate M1 connectivity comment 10003 preserved |
| AIS-2 | Standard complete case; approved internal comment 10005 |
| AIS-3 | Missing access level and justification; approved internal comment 10006 |
| AIS-4 | Automatically discovered/classified in dry-run; no comment |
| AIS-5 | Automatically discovered/classified and posted under separate one-action approval; internal comment **10007** |

The original M3 acceptance verified exact body, original author, `public: false` and one matching comment. A later scheduled cycle and a real worker restart added zero POSTs and retained the same verified operation/comment and consumed budget. Status/assignment snapshots and protected tickets were unchanged. All unattended-write gates were then disabled.

The final interview check independently made **12 guarded GETs and zero mutations**. It reverified AIS-5/comment 10007's exact body/author/internal visibility, one match, and unchanged AIS-1 through AIS-5 project/status/assignment/comment snapshots. It neither manually processed tickets nor replayed a write test. No approval or provisioning operation was sent. This report does not claim a new browser UI screenshot or customer-view visibility test.

## 4. Native operation and instruction validation

The runbook commands were executed: authenticated status/health, graceful stop, detached start, log inspection and completed-poll observation. A new worker run ID recovered the same five source hashes, operation IDs, comment IDs and processing timestamps. Startup health returned 503 while waiting for the current run's first poll, then 200 / dry_run after it succeeded. A later cycle skipped all five unchanged requests. Socket inspection showed the listener on 127.0.0.1:8765.

At the final interview review the service was running in dry-run. The later publication check found no listener at the configured local health endpoint; see [publication verification](PUBLICATION.md). Native startup requires the installed environment/configuration and an available Windows host/session. Closing the launcher is supported and tested; VS Code itself was not terminated for the test. No reboot/logon task or Windows Service supervisor was installed. Logs are local append-only files; rotation/retention is not implemented.

Recovery instructions match the journal behavior: preserve state, wait for persisted Retry-After deadlines, investigate uncertainty, and never reset/delete the journal to force an effect. A fresh final-review backup was reopened with integrity `ok`, matching journal/job/budget row counts and retained verified comment 10007 plus its consumed reservation. Full replacement of a deployment database and live outage/crash recovery were not exercised.

The demo's local `show`/`audit` commands and selected historical log line were executed/checked without processing a ticket. Its six spoken segments total 235 words; rehearse the timing with screen changes rather than claiming a measured speaking duration.

## 5. Untested production capabilities

| Capability / assumption | Outstanding evidence |
| --- | --- |
| Docker/Compose | Docker unavailable; no image build, Linux runtime, volume migration/restore or container restart validated |
| Resilience | Live outage/crash drills, end-to-end restore, disk exhaustion, host reboot and process supervision |
| Scale / service levels | Representative queue volume, latency distribution, sustained workload and availability targets |
| Enterprise security | Managed identities/secrets, rotation/revocation, TLS/SSO/RBAC, file ACL/retention review, vulnerability assessment |
| Organization-wide integration | Jira identity coverage, actual plan/native approvals, authoritative catalogue/reviewer ownership, other systems' schemas/permissions |
| Business benefit | Manual baseline, measured effort/clarification reduction, customer adoption, satisfaction or ROI |

These are adoption decisions and validation gates, not hidden delivered features. Future external provisioning or broader write authority needs a separate requirements, security and approval process.

## Traceability

- [Code review](CODE_REVIEW.md): narrow health/pagination/ignore fixes and residual risks.
- [Results](RESULTS.md), [native runbook](RUNBOOK.md), [M3 acceptance](MILESTONE3_ACCEPTANCE.md), [consumed policy/body](MILESTONE3_WRITE_POLICY.md).
- Ignored current evidence: `reports/interview-final-verification.json`, `reports/interview-live-readback.json`, `reports/interview-startup-health.json`, `reports/interview-before-restart.json`, `reports/interview-ignore-audit.json`, `reports/offline-tests.xml` and native logs.
- Historical evidence: passed `reports/milestone3-automatic-write.json`, policy approval record, earlier milestone reports and SQLite/backup journals.

Only the deliberately selected synthetic case summaries and existing comment should be shown during the interview. Detailed reports/database/logs remain private local evidence.
