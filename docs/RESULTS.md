# Actual results

Feature-branch experiment, October 20: [Groq extraction evaluation](GROQ_EVALUATION.md) measured 70.8% to 94.2% field correctness on 40 authored synthetic requests, with higher manual triage and provider failures. The readiness gate did not pass; AI stays disabled and separate from the operational pipeline. The original 186 tests are retained; 68 focused prototype cases bring the branch suite to 254. No Jira call or write was made by this experiment. The public `main` branch is not changed by the experiment.

Observed October 19, 2026. **Milestones 1, 2 and 3 pass within the verified sandbox scope, using the tested native Windows fallback.** The background worker automatically discovered/classified AIS-4 in dry-run and AIS-5 under a separately approved one-action policy, posting internal comment `10007`. Independent Jira reads, later polling and a real worker restart verified one matching comment and persistent SQLite state. Unattended writes are now disabled; the healthy worker continues in dry-run. Docker runtime remains untested. This is not a production-readiness claim.

| Measure | Observed result |
| --- | --- |
| Initial repository | Empty directory; no existing code or instructions found |
| Local Python | 3.11.17 via local launcher; isolated `.venv` installed |
| Offline tests | Final interview review: 186 passed, 0 failed, 0 skipped; JUnit suite time 8.45 seconds; all original 177 cases retained; local `reports/offline-tests.xml` |
| Lint | `ruff check src tests scripts` passed |
| Formatting | All 36 Python files passed `ruff format --check src tests scripts` |
| Dependencies | `pip check`: no broken requirements |
| CLI startup | `python -m accessflow --help` ran successfully |
| Missing-config behavior | Offline regression still verifies redacted error/exit 2; local credentials now configured |
| Jira authentication | Replacement v2 token passed the active-identity check through the scoped gateway |
| Real request read | Platform and JSM reads verified AIS-1/10006, AIS-2/10007, AIS-3/10008, AIS-4/10009, AIS-5/10010; desk 2; request types 10 and 9 |
| Jira write | M1 connectivity 10003 and M2 internal comments 10004/10005/10006 preserved; worker automatically posted the separately authorized AIS-5 internal comment 10007 |
| Actual subscription/approval capability | Unknown |
| Milestone 1 | PASSED for live connectivity and controlled comment/restart verification |
| Milestone 2 | PASSED: all three real cases classified, authorized internal write/read-back verified, repeat/fresh-process checks passed |
| Milestone 3 | PASSED with native fallback: automatic discovery/classification/write, live read-back, subsequent-poll and worker-restart checks, safe controls and write disablement |
| Live requests processed | 5 distinct requests classified; 4 triage comments plus the separate M1 connectivity comment; AIS-4 remains dry-run with no comment |
| Live duplicate prevention | M2 repeats made zero POSTs; M3 later scheduled poll and real worker restart also added zero POSTs; one matching triage comment per written request |
| Live verification duration | M1 sequence: 8.186 seconds; M2 sequence: 38.195 seconds, including preflight, all writes/read-backs, repeats, restart and final snapshots; not per-request processing latency |
| M3 automatic-write poll | AIS-5 discovery/classification/write cycle: 9.519 seconds; includes the full five-request scan, not per-request latency or a throughput estimate |
| Live per-request latency/time savings/manual steps removed | Not measured |
| Deployment | Hidden detached Windows process and local authenticated API tested through startup, stop and restart; Docker not found on PATH, image/Compose untested |

## October 20 public release checks

The public README was reduced to the business problem, an architecture diagram, implemented scope, verified evidence, fresh-clone setup and links to detailed documentation. Account-specific runtime assumptions were removed from the setup/runbook. Unused LLM configuration placeholders were removed from `.env.example`; application functionality was preserved.

A source-only export was installed in a fresh virtual environment using the locked dependencies and editable package installation. All **186 tests passed**, with zero failures/errors/skips; Ruff lint, formatting of 36 Python files and dependency consistency checks passed. An additional offline configuration smoke check used synthetic non-AIS project/desk/type identifiers and confirmed the documented admin-token generation preserves an existing value. Neither check contacted Jira.

Loose token files were moved to restricted Windows LocalAppData storage outside the checkout. The ignored runtime `.env`, journals and raw evidence remain private. Git exclusions now also cover backup directories and common backup/dump patterns. The destination repository was public and empty before the initial commit; commit identity uses GitHub noreply email. Staged files and reachable history are audited before pushing. Publication state and hosted CI are recorded in [publication verification](PUBLICATION.md). Unattended writes remain disabled; Docker remains unverified.

Initial release `4146c23` was published to [Eklavya20/accessflow-jira](https://github.com/Eklavya20/accessflow-jira). The remote commit, complete file tree and README matched the audited local source. [Hosted Windows/Python 3.11 CI run 39332809467](https://github.com/Eklavya20/accessflow-jira/actions/runs/39332809467) completed successfully; its logs confirm **186 passed**, Ruff lint, formatting of 36 Python files and dependency checks. This is fresh-runner offline evidence, separate from the historical live Jira acceptance.

## Public repository preparation

Publication cleanup added the selected MIT license and a Windows/Python 3.11 offline CI workflow, replaced identifying account/machine/audience context with public examples, and initialized branch `main`. The exact disabled sandbox policy and original presentation documents remain private and ignored; `.env` selects the private policy. Its consumed approval and SQLite state were preserved.

The 71-file staging area passed the credential/account-literal scan, 36 private-path/five public-path ignore checks, relative-link checks and whitespace checks. An export of only the staged source, without `.env`, token files or the historical database, passed all 186 tests, lint, formatting and dependency checks using the existing environment. A wheel built offline includes the MIT license. The check runner uses a fresh temporary directory to avoid stale Windows permissions. See [publication verification](PUBLICATION.md) and private `reports/publication-audit.json`.

No commit, remote, hosted CI execution or new Jira action was performed. Configured write gates remain disabled. The local health endpoint refused the publication-time connection; historical native/Jira evidence above is retained, and no current running-service claim is inferred from it. Docker remains unverified.

## Final interview-readiness review

The final manual review corrected readiness inherited from a previous worker run, health mode precedence and acceptance of empty pagination without completion metadata. It expanded SQLite/log ignore coverage without changing business rules, schemas, dependencies or write scope. All 177 original cases remain; nine regressions bring the suite to **186 passing**. The [review record](CODE_REVIEW.md) describes findings and limits.

Native stop/start and recovery instructions were re-executed in dry-run, observing 503 until the new run's own poll succeeded, then health 200 with unchanged five-ticket persistence and a zero-work repeat poll. A fresh backup reopened with matching journal/job/budget counts and integrity ok. An independent final Jira check made 12 GETs and zero mutations, reverified AIS-5/comment 10007 and unchanged snapshots for all five tickets. All unattended write gates remain disabled.

Real Git ignore-engine checks confirmed 21 private path cases excluded and five intended public paths included. A scan of 67 source/config/documentation/build files found no current credential values; the project had no Git index/history at that review. Subsequent [publication preparation](PUBLICATION.md) initialized and audited the local staging area. Local evidence is saved under ignored `reports/interview-*.json`. The [interview pack](INTERVIEW_PACK.md) includes the product brief, business analysis, architecture, Q&A, a 235-word timed demo and [final evidence matrix](FINAL_VERIFICATION.md). Docker/Compose remains unverified; there is no new production-readiness or business-savings claim.

## Milestone 3 — passed with verified native Windows operation

The existing processor/client/journals are preserved. New modules implement scoped polling, durable job checkpoints/retry deadlines, worker locking and status, a separately bounded write capability, and authenticated FastAPI operations. Runtime/development dependency locks, Dockerfile, build-context allowlist, Compose volume/health/restart configuration and a native Windows launcher are provided. No LLM, Redis, external queue or public endpoint was introduced.

| Phase / evidence | Observed result |
| --- | --- |
| A — first live scoped discovery | Existing JSM request-list capability worked for AIS desk 2 and types 9/10; 3 requests discovered/classified; 50 GETs, 0 writes, 0 failures |
| B — new real request | User created AIS-4 manually; background worker discovered issue ID 10009 without a manual processing command |
| AIS-4 classification | GitHub / Read-only / `Verifying independent AccessFlow polling in the sandbox.`; `ready_for_human_fulfillment`; no missing information |
| Automatic completion | Worker log and SQLite audit record `worker_request_completed`, mode `dry_run`, at 20:02:35.516 UTC / 22:02:35 Europe/Paris |
| Subsequent real poll | Discovered 4, processed 0, skipped 4, failed 0; AIS-4 remained one processing result with no comment ID |
| C — actual native startup | Launcher started a hidden detached process, exited, and the service continued polling on loopback port 8765 |
| Actual stop/restart | Authenticated shutdown closed the service; a fresh service/worker run ID recovered the same AIS-4 result, source hash and processing timestamp |
| After restart | Health HTTP 200 in dry-run; discovered 4, processed 0, skipped 4, failed 0; AIS-4 result count still 1 |
| Live administrative controls | Unauthenticated status returned 401; authenticated status/result/audit worked; retrying completed AIS-4 returned 409 and did not schedule redundant work |
| SQLite backup | SQLite backup API produced a copy; reopening it returned integrity `ok` and matched connectivity, triage-operation, audit and worker-job counts at the snapshot |
| Unattended safety | The one-action policy was separately approved and consumed; now policy approved=false, worker-write enabled=false, global dry-run=true and configured approved hash blank; durable budget retained |
| D — bounded policy | [Concrete review](MILESTONE3_WRITE_POLICY.md) explicitly approved for AIS-5/type 9, standard-ready outcome, one internal action total and exact activation hash |
| E — new real request | User manually created AIS-5 after activation; worker discovered issue ID 10010 without a manual processing command |
| E — automatic Jira write | Exactly one worker POST, HTTP 201 at 22:26:49.806 Europe/Paris, solely to AIS-5's JSM comment endpoint; internal comment 10007 |
| Independent read-back | Exact body, original authenticated author and public=false verified separately; exactly one matching marker/comment |
| Later scheduled cycle | Same worker run: discovered 5 / processed 0 / skipped 5 / failed 0; no additional POST |
| Real worker restart | Fresh service/worker run recovered the same verified operation/comment 10007; its completed cycle skipped all five; no additional POST |
| Protected Jira state | AIS-1/2/3/4 snapshots unchanged; AIS-5 status and assignee fingerprint match the pre-comment audit; no status/assignment/approval/provisioning mutation sent |
| Final read-only service | Restarted after disabling all write gates; health 200 / mode dry_run; independent read-back still found one exact internal comment |
| SQLite persistence/backup | Verified operation/comment and one consumed policy-budget reservation survive restart; a fresh backup reopens with integrity ok and the same verified comment/budget |
| Docker runtime | `docker` unavailable on PATH; no image build, Compose startup, Linux/container restart or volume restore claimed |

AIS-4's exact operation marker is `e53606ab1c9b91fcf4cde8316c26c28e462b2f79caff25ecd24e56f396e08ac4`; its dry-run body SHA-256 is `0b92d4fb1b38b57afdb50823c1b71a6a9e8003f439f3b84f9ac8113449a911ae`. The example is preserved in the write-policy review but is excluded from its permitted write target. No manual `process AIS-4` command or Jira comment POST was used for this acceptance.

AIS-5 was classified GitHub / Read-only / `Verifying bounded automatic internal triage in the sandbox.` / `ready_for_human_fulfillment`. Its scheduled poll ran 20:26:41.027–20:26:50.546 UTC (22:26:41–22:26:50 Europe/Paris), taking 9.519 seconds. The worker verified comment 10007 at 20:26:49.989 UTC. Exact body SHA-256: `75b1857fd8e0861adebadb85b35bd6e3e3aa5aa030d21214ec54f9485a4267e9`; operation marker: `c321d896dd15e3f2758472eb641bde82bb1c11a9202fcb017eacfdc321193e61`. The consumed activation policy hash is `5f8ddabbefe9c15410294cf73ff9ea6a0cb8e784618687233d11ec43159e3808`.

The independent observer made 57 GETs across preflight, after-write, repeat, restart and disabled stages, with zero mutations. The worker's entire logged mutation trace contains exactly one POST, returning 201 for `/rest/servicedeskapi/request/10010/comment`; repeat/restart added zero. Before/after total comment counts are AIS-1 2→2, AIS-2 1→1, AIS-3 1→1, AIS-4 0→0, AIS-5 absent→1. Status remains Waiting for support (10002), assignment fingerprints match, and no approval/provisioning action occurred. No manual processing or retry command was issued for AIS-5.

SQLite retains one verified AIS-5 operation with comment 10007 and one durable policy-budget reservation. The initial automatic job saved a dry-run plan (result 21) followed by the authorized write result (22). Unchanged polling/restart created no new result/effect. Disabling write mode caused one automatic local dry-run reevaluation of its changed execution configuration; it reused the same verified operation/comment and posted nothing. This is configuration reevaluation, not a second Jira action. AIS-4 remains one result with no comment. Existing connectivity and M2 journals are preserved.

Ignored local evidence: `reports/milestone3-initial-poll.json`, `reports/milestone3-AIS-4-first-and-repeat.json`, `reports/milestone3-native.json`, `reports/milestone3-policy-approval.json`, passed `reports/milestone3-automatic-write.json`, `reports/native-service.stderr.log`, exact body exports, backup files under `data/`, and the existing SQLite database. The worker log includes method/path/status events without authorization headers or bodies. Offline worker-write tests remain separate from this live authority/evidence.

At the Milestone 3 gate, 177 tests covered discovery/pagination, duplicate events, changed source, requester corrections, self-comment/status loops, audit, retries/deadlines, auth, locking, shutdown/health, budgets and policy denial, schema upgrade, supervisor exit and bounded write/reconciliation/restart. Final interview review preserved those cases and added nine health/pagination regressions, bringing the suite to 186. One dependency deprecation warning from Starlette/AnyIO remains; there are no failed/skipped tests. No live outage or crash fault was induced.

Native process independence was verified after its launcher exited; the user's VS Code window was not closed or terminated. The host/session must stay available. The native launcher does not install Windows Service or reboot/logon supervision. Docker runtime verification, sustained workload/latency measurements, real recovery drills, production identity/secret operations, ownership and retention remain future work. No labor saving, ROI or enterprise readiness is inferred.

The first pytest run produced 49 setup errors because the sandbox could not access pytest's default Windows temporary directory. No tests were skipped. A workspace-local temporary directory resolved that infrastructure issue. Additional safety checks brought the suite to 59 passing tests. The first PowerShell wrapper was blocked by the machine's script execution policy; it was replaced with `scripts/check.py`, which uses Python without changing that policy. Dependency downloads initially hit sandbox network restrictions; the reviewed dependency installation succeeded.

## Milestone 2 — passed live CLI/comment acceptance

The typed processor, configurable catalogue, deterministic parser/policy, real Jira ingestion, durable processing results/operations/audit, per-issue OS lock, exact-hash authorization, internal-only comment writer, uncertainty reconciliation and CLI are implemented. No new runtime dependencies were added. The existing Jira transport, authentication, allowlist and connectivity probe are preserved.

| Evidence | Actual result |
| --- | --- |
| Offline acceptance | 127 passed, 0 failed, 0 skipped; original 59, 56 processor/CLI tests, and 12 live-verifier boundary tests |
| Four outcomes | Standard complete, missing details, privileged, and unknown/ambiguous cases passed offline |
| Real AIS-1 read/dry-run | Demo Analytics; Administrator; expected justification; `privileged: true`; `privileged_review`; no missing/uncertain fields |
| Real AIS-2 read/dry-run | GitHub; Read-only; expected documentation justification; `ready_for_human_fulfillment`; no missing/uncertain fields |
| Real AIS-3 read/dry-run | GitHub; no level/justification; `needs_information`; exactly Access level and Business justification missing |
| Real request types/status | AIS-1: Request admin access (`10`); AIS-2/AIS-3: Get IT help (`9`); all Waiting for support |
| Durable live processing | Revision 1 operations now `verified`; comment IDs 10004, 10005, 10006 respectively |
| New-process local inspection | Separate CLI `show`/`audit` processes recovered verified results 14, 15 and 16 and their comment IDs; audit event counts 13, 12 and 12 |
| Preserved Milestone 1 state | Connectivity operation remains `verified`, internal comment `10003` |
| New triage write-back | Exactly 3 POSTs received HTTP 201; exact approved bodies, authenticated author, and `public: false` separately read back |
| Standard/incomplete real tickets | User manually created AIS-2 and AIS-3; both read and classified successfully |
| Repeated new triage effects/restart | All same-process and fresh-interpreter runs returned `already_verified`, same IDs, 0 additional POSTs |
| Concurrency | OS lock blocked a competing thread and a separate interpreter; lock became available after release |
| API failure | Read 429/503 recovery and definitive 401/403 retries; uncertain timeout/429/503 writes reconciled offline without resending |
| Authorization boundary | Exact comment hash required; public/approval/status/assignment/provisioning actions absent from the triage workflow |
| Default configuration | Dry-run remains true; token files retained and excluded from source control |

Local evidence: ignored per-ticket dry-run reports, `reports/milestone2-previews.json`, the original proposal manifest, explicit `reports/milestone2-approved.json`, completed `reports/milestone2-live.json`, exact comment text exports, `reports/offline-tests.xml`, and `data/accessflow.db`. Requester profiles/email are not included in processing results. The initial additions passed 101 tests but exposed two lint errors, which were corrected. Three later CLI tests initially had a fixture-discovery setup error; moving the shared fixture to `conftest.py` resolved it. The earlier complete suite passed 115 tests; adding 12 scope-guard cases brought the final suite to 127 passing tests. None was skipped.

The exact reviewed comments and hashes remain in [the write review](MILESTONE2_WRITE_REVIEW.md). The earlier preview/preflight trace recorded 34 GET responses; an earlier preflight attempt stopped after two additional GETs because of a local script quoting error. Those preview attempts issued no write. The user then explicitly approved the three exact internal comments. A fresh dry-run of all three matched those hashes before the first POST. The agent created no tickets.

The live acceptance sequence ran **20:59:17–20:59:55 Europe/Paris** on October 19, 2026 (18:59:17–18:59:55 UTC), measured at 38.195 seconds. Parent and fresh-process traces captured 199 requests in total: 196 GETs and exactly 3 POSTs. Only the initial-write phase could send one exact approved internal comment per ticket; repeat/final phases rejected all writes before transport. No status, assignment, approval-decision, public-comment, other-ticket, or external-permission mutation was sent.

| Ticket / result | New internal comment ID | First run | Same-process repeat | Fresh-process repeat | Exact triage matches after | Total comments before → after |
| --- | --- | --- | --- | --- | --- | --- |
| AIS-1 / privileged review | 10004 | created_and_verified | already_verified / 10004 | already_verified / 10004 | 1 | 1 → 2 (preserves M1 comment) |
| AIS-2 / ready for human fulfillment | 10005 | created_and_verified | already_verified / 10005 | already_verified / 10005 | 1 | 0 → 1 |
| AIS-3 / missing information | 10006 | created_and_verified | already_verified / 10006 | already_verified / 10006 | 1 | 0 → 1 |

Each exact body, versioned marker and authenticated author was read back through Jira; all three returned `public: false`. All statuses remained Waiting for support (`10002`). Assignment fingerprints matched before/after without storing assignee profiles in the evidence. All three operations are durably verified in SQLite, and the separate M1 operation is still verified as internal comment 10003. Persistent `.env` dry-run remains true; the approved writes used per-run in-memory settings only.

**Milestone 2 passed** its agreed gate with 127 tests and the CLI/comment evidence above. That restart was a new Python interpreter/HTTP client reopening SQLite. The later Milestone 3 section separately records an actual native worker restart. No container/host reboot, live outage or concurrent Jira mutation test is claimed. Native approval entitlement and richer routing permissions remain unverified.

## Passed Milestone 1 live verification with the replacement token

The scoped-token identity check and full `accessflow check` completed successfully. The report confirms AIS project membership, JSM request access, desk/type mappings, all nine discovered request types, required field metadata, effective issue permissions, and available transitions. Native approval reads remain disabled. Read evidence is in ignored `reports/milestone1-read.json`; the read-only discovery command's `milestone_1: incomplete` field describes that command's scope, not the subsequent aggregate live verification outcome.

The approved comment was tested from **20:05:25 to 20:05:33 Europe/Paris** on October 19, 2026 (18:05:25–18:05:33 UTC). `scripts/verify_milestone1.py` recorded the following against real Jira:

| Check | Actual result |
| --- | --- |
| Exact matching comments before | 0 |
| Initial operation | `created_and_verified`; comment ID `10003` |
| Visibility and content read-back | `public: false`; exact approved body and authenticated author verified by separate GET |
| Same-process repeat | `already_verified`; comment ID `10003`; no second POST |
| Fresh-process repeat | New Python interpreter and HTTP client reopened the same SQLite file; `already_verified`, same comment ID; 0 POST attempts |
| Exact matching comments after all runs | 1 |
| Remote mutation attempts | Exactly 1 POST, exclusively to `/rest/servicedeskapi/request/10006/comment` |
| Durable journal | One `verified` record with comment ID `10003`, internal visibility, and bound body hash |
| Ticket status before / after | Waiting for support / Waiting for support |
| Aggregate live verification | `passed: true` |

Exact approved and posted text:

> AccessFlow integration verification: this is an automated test comment created in the AIS sandbox. No access has been granted and no approval decision has been made.

Evidence is retained locally in ignored `reports/milestone1-live.json`, `reports/comment-approval.json`, and `data/accessflow.db`. The verifier captured method/path traces without headers or tokens. A request guard limited the initial process to one exact approved POST and prohibited every POST in the fresh-process recheck. No approval endpoint, workflow transition, field edit, other-ticket write, or access-provisioning operation was sent. The persistent `.env` remains in dry-run mode; write enablement was limited to this approved test's in-memory settings.

This proves the earlier CLI/connectivity restart behavior. Milestone 3 subsequently verified a native worker restart; container/host restart remains untested. API fault handling remains tested offline only.

## Earlier live read-only verification (superseded token)

The Cloud ID was obtained through the documented site `/_edge/tenant_info` endpoint. The ignored local `.env` now selects the scoped gateway, AIS allowlist, project ID `10001`, service desk ID `2`, and test issue `AIS-1`. Tokens/account identity are absent from this document. Redacted evidence is retained locally in ignored `reports/live-read.initial.json`.

| Real GET | HTTP result / observation |
| --- | --- |
| `/rest/api/3/myself` | 401; stopped without repeat |
| `/rest/api/3/project/AIS` | 200; service desk project `10001` |
| `/rest/api/3/issue/AIS-1` | 200; stable issue ID `10006` |
| Issue content | Expected title; Demo Analytics; Administrator; expected business justification; sandbox and no-access-grant notices present |
| Current status | Waiting for support |
| `/rest/api/3/mypermissions` in issue context | 200; Browse, Comment, Edit, Transition, Assign reported true |
| Issue transitions | 200; Respond to customer, In progress, Escalate, Cancel request, Pending, Resolve this issue observed; none executed |
| Issue edit metadata | 200; editable field metadata observed, including labels; no field changed |
| JSM service desks and request types | 200; AIS desk `2`; Request admin access type `10` exists |
| Request type fields | 200; summary required; description/attachment optional in portal configuration |
| `/rest/servicedeskapi/request/AIS-1` | 401; stopped without repeat |
| Comment/approval writes | 0; no comment, decision, provisioning, status or field change |

The earlier token's supplied scopes omitted `read:jira-user`, documented for the identity endpoint, and `read:user:jira`, required alongside the supplied granular JSM request/comment scopes. Those omissions were consistent with the observed endpoint-specific 401 responses. The user subsequently provided the v2 token; refreshing local configuration resolved these read blockers, as demonstrated above. Effective issue permissions and token scopes are separate requirements.

Approval reads are now opt-in via `JIRA_QUERY_APPROVALS`; no native approval entitlement is inferred from field names or transition availability. No approval API was queried with a known-missing approval scope.

Credential protection: `.gitignore` covers `jiratoken.txt`, bare `jiratoken`, local token text files (including the old-token copy), `.env` variants (except `.env.example`), credential JSON, private keys and common secret directories. The directory initially had no Git repository. Publication preparation subsequently initialized a local repository and audited the staged files; credentials remain excluded, with no project commits yet. Exposure in other copies cannot be established from this workspace. Token files have been retained at the user's request.

## Scope of offline evidence

Tests cover Cloud URL and secret configuration safety, target and allowlist validation, project/service-desk/type/field discovery, metadata-only reporting, explicit optional-capability failures, read pagination, 401/403 and other permanent errors, 429/500/503 bounded retries, timeout exhaustion, numeric/date Retry-After handling, long wait deferral, redirect refusal, dry-run protection, comment write/read-back, visibility, repeated runs/fresh-client restart, concurrent SQLite reservations, and reconciliation after an uncertain POST.

HTTP responses in offline tests are isolated fixtures. Separate real evidence verifies AIS-1/2/3 approved CLI comments, AIS-4 autonomous dry-run and AIS-5 separately approved automatic internal comment 10007, independent read-back, scheduled repeat, native worker restart and final write disablement. Docker runtime and live fault-injection/restore drills remain untested.

## Next evidence required

Milestone 3's sandbox/native gate passes. The single AIS-5 approval is consumed and unattended writes are disabled; future write targets/actions require a new bounded review and explicit approval. Before broader rollout, validate Docker or the intended supervised deployment, sustained workload and live recovery/restore drills, secret rotation, alerting, retention and failure ownership. Human authorization/fulfillment remain separate. Token files have been retained; remove/move redundant copies only with user permission.
