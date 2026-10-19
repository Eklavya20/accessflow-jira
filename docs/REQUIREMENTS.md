# Requirements and acceptance

Status: Milestones 1, 2 and 3 passed within their verified sandbox scope using the native Windows fallback. Milestone 3 adds polling, durable retries and authenticated FastAPI operations. AIS-4 passed autonomous dry-run; AIS-5 passed separately approved automatic internal write/read-back, later-poll and native worker-restart checks. The consumed one-action policy is disabled and the running worker is dry-run. Docker runtime verification and broader production requirements remain outstanding. See [current acceptance](MILESTONE3_ACCEPTANCE.md).

## Functional requirements

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| F01 | Authenticate to real JSM and discover configuration | Live active identity, project/desk/type/field report |
| F02 | Retrieve only configured project requests for processing | Actual project ID/key validation; unauthorized-project rejection |
| F03 | Extract application, access level, justification without LLM | Labeled deterministic cases, discovered field mappings |
| F04 | Validate complete and unknown-application requests | Valid request routed; unknown application held for review |
| F05 | Request missing details once | Real clarification comment; repeated run adds none |
| F06 | Reevaluate new relevant information | Updated fields/customer comment changes outcome correctly |
| F07 | Escalate sensitive permissions | Authorized human route; no provisioning or automatic approval |
| F08 | Observe native approval records where configured | Actual human decision via JSM approval API; otherwise documented manual review |
| F09 | Apply configured Jira updates | Read-back of allowed fields/status/assignment; no guessed IDs |
| F10 | Persist execution and audit history | Durable request/action records survive restart |
| F11 | Recover bounded transient failures | 429/5xx/timeout retries without repeated successful effects |
| F12 | Provide operational controls | Health/outcomes/failures/retry/dry-run/audit through authenticated admin API or CLI |
| F13 | Run independently of VS Code | Demonstrated worker/container restart with persistent state |

## Non-functional requirements

Default read-only behavior; explicit comment visibility; HTTPS and secrets outside source control; allowlisted projects verified using actual Jira metadata; concurrency protection; stable issue IDs; durable effect intentions; uncertainty reconciliation; bounded retries honoring rate limits; redacted structured logs; reproducible dependencies; maintained documentation. Never claim distributed exactly-once execution. A local deployment requires an available, powered-on host.

## User stories

- As an employee, I receive a clear list of missing details so I can complete my request.
- As an IT agent, I see complete requests prepared for the correct team so I can focus on fulfillment.
- As a security reviewer, I retain sensitive-access decisions and can inspect the request's audit history.
- As an operator, I can inspect failures, reconcile uncertain writes, and restart safely.
- As a product owner, I can distinguish measured benefits from assumptions and evaluate remaining adoption work.

## Test scope and final acceptance

The 127 offline tests preserve the original 59 cases and add all four business outcomes, labeled/ADF extraction, catalogue uncertainty, sensitive prose, requester corrections, exact-hash approval, internal-only write-back, revision changes/reversions, repeated processing, denied permission retries, uncertain older revisions, crash-before-local-success reconciliation, cross-process OS locking, local CLI inspection, and live-verifier mutation guards. Separate [live evidence](RESULTS.md) proves the three authorized internal comments and repeat/restart checks.

Worker/admin tests extend coverage to scheduled processing, durable retries/deadlines, authenticated controls, policy budgets and worker restarts. Separate real evidence verifies AIS-4 autonomous dry-run, AIS-5 approved automatic internal write/read-back, subsequent polling, native worker restart and local API controls. Controlled live failure recovery and intended deployment runtime/restore acceptance remain necessary before broader rollout.

Final acceptance requires all ten outcomes in [the live procedure](LIVE_ACCEPTANCE.md): real authentication/read/write, all three workflow scenarios, repeated-run duplicate prevention, API failure recovery, restart persistence, and reproducible operation. Any unsupported Jira feature must be recorded with a precise revised scope; mocks cannot replace these checks.
