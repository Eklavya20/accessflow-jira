# AccessFlow business analysis

## Evidence behind discovery

Discovery so far consists of the project owner's brief, follow-up constraints, explicit approvals, actual Jira API observations and five synthetic acceptance tickets. No interviews with external organization employees, production users or enterprise security teams were conducted. The roles and questions below are a discovery plan for adoption, not invented interview findings.

The agreed problem is repetitive preparation of application-access tickets. The target outcome is consistent classification and a usable next action while humans retain authorization and fulfillment. Through the milestones, scope narrowed to internal comments because those effects were authorized and verified; native approval configuration and richer routing were not assumed.

## Stakeholders and discovery questions

| Role | Need / proposed responsibility | Questions to validate |
| --- | --- | --- |
| Requester | Understand missing information | Which fields are confusing? How should IT request clarification? |
| IT support | Prepare requests consistently; own fulfillment | Which cases consume effort? What makes a request complete? Which catalogue/queue filters are correct? |
| Application owner / security reviewer | Retain sensitive-access authority | Which levels require review? Who can authorize? Where is the authoritative decision recorded? |
| Jira administrator | Confirm real API/workflow capabilities | Which identity can see eligible requests and internal comments? Which scopes, plan and workflow apply? |
| Service operator | Run and recover the integration | Who owns failed/uncertain work, token rotation, host availability, backups and retention? |
| Product owner | Balance value, risk and operating cost | Would native automation suffice? What pilot evidence justifies a custom service? What is an acceptable failure/manual-review rate? |

Named operational owners, workload, retention periods, service targets and production catalogue policy remain unconfirmed. No prospective adopter's internal process or requirement is inferred.

## Requirements and prioritization

| Priority | Requirement | Delivered boundary |
| --- | --- | --- |
| Must | Read real eligible JSM requests automatically | AIS project/desk and configured request-type allowlists, paginated discovery |
| Must | Validate application, access level and justification | Deterministic English labels/ADF and small configurable catalogue; ambiguity held for humans |
| Must | Explain complete, incomplete, privileged and unknown cases | Four typed outcomes; three scenarios live, unknown/ambiguous offline |
| Must | Prevent unauthorized/duplicate remote effects | Internal-only triage writer; exact CLI hash or separate bounded worker policy; durable intentions and reconciliation |
| Must | Persist and inspect work; survive restart | SQLite results/audit/jobs/retries and authenticated local controls; native restart verified |
| Must | Run outside an editor | Detached Windows process tested; host/session availability required |
| Should before rollout | Appropriate deployment, identity and ownership | Docker unverified; supervisor, production identity, alerting, retention and failure owner still needed |
| Should before rollout | Validate recovery and value at expected volume | Live outage/crash and full restore drills; workload and pilot measurements outstanding |
| Could after a separate decision | Integrate authoritative catalogue/identity systems | No such integration or provisioning authority currently exists |

Excluded: granting/revoking access, automatic approval, ticket transitions/assignments, public worker comments, arbitrary projects, LLM extraction, complex frontend and distributed infrastructure.

## User stories and acceptance criteria

| ID / story | Acceptance criterion | Evidence |
| --- | --- | --- |
| BA-01: As IT support, I want new requests prepared automatically | Given an eligible portal request, a scheduled worker cycle discovers and classifies it without a manual processing command | AIS-4 and AIS-5 worker logs/audit |
| BA-02: As a requester, I need missing fields identified | Given GitHub without access level/justification, the result names exactly those missing fields for IT to request | AIS-3; internal comment 10006. Direct customer contact remains human work |
| BA-03: As a reviewer, I retain privileged decisions | Given Administrator access, output requires authorized human review and never grants/approves it | AIS-1, internal comment 10004; no approval/provisioning mutation |
| BA-04: As the owner, I control write scope | Without approved unexpired policy bytes, matching hash/flags and target limits, the worker cannot post | Offline denial tests; current disabled gates verified. One separately approved AIS-5 action succeeded |
| BA-05: As an operator, I avoid repeated effects | Given unchanged source or an existing verified effect, later polling/restart preserves one comment and its operation ID | AIS-5 comment 10007, zero repeat/restart POSTs |
| BA-06: As an operator, I can inspect/recover work | Results/errors/retry times/audit persist; authenticated retry schedules only eligible failed work without clearing uncertainty | Offline failure tests, live admin auth/health and completed-job retry rejection |
| BA-07: As a product owner, I see honest evidence | Test fixtures, real acceptance and untested deployment/production capabilities are reported separately | [Final verification](FINAL_VERIFICATION.md) |

Changed requester information and API-failure cases are offline-tested; they were not induced live. A matching Jira comment is evidence of triage, never evidence that access was authorized or granted.

## Risks and responses

| Risk | Existing response | Remaining adoption gate |
| --- | --- | --- |
| Wrong project/type/permission or poor visibility | Validate actual IDs and allowlists; fail closed; no silent permission expansion | Confirm production identity, scopes and coverage with admin |
| Duplicate comment after timeout/crash | Durable pending intent, per-issue lock, marker/body/author reconciliation; never blindly resend uncertainty | Live recovery drill; documented human resolution for an absent uncertain effect |
| Incorrect or ambiguous extraction | Conservative deterministic outcomes and human review | Validate catalogue/schema on representative labeled requests |
| Token/data exposure | Secrets outside source, ignore rules, local admin authentication, redacted error events | Managed secrets, ACL/retention review, rotation/revocation validation |
| Workstation outage or growing queue | Durable checkpoints and bounded backoff; visible health/status | Supervised deployment, volume measurements, alerts and named failure owner |
| Custom service costs exceed value | Explicit native-versus-Python comparison | Validate simple native implementation before committing to long-term hosting |

## Planning and decision gates

| Stage | Exit evidence / decision | State |
| --- | --- | --- |
| M1: prove API feasibility | Real authentication/read and one approved connectivity comment, repeat/restart check | Passed; comment 10003 |
| M2: prove rules and controlled effects | Standard/incomplete/privileged cases, exact approved internal comments, audit and duplicate checks | Passed; comments 10004–10006 |
| M3: prove autonomous operation | Automatic new requests, separately approved bounded write, native restart, controls and disabled writes afterward | Passed with native fallback; AIS-5/comment 10007 |
| Interview preparation | Narrow review fixes, regression checks, honest evidence, rehearsable two-minute story | Final review pack; no new Jira writes |
| Pilot proposal | Choose native/custom approach, named reviewers/operator, least privilege, privacy/retention, volume and recovery targets | Not authorized or implemented as a rollout |
| Production decision | Intended runtime, live recovery/restore, secure operations and measured pilot results accepted by owners | Outstanding |

Before a demonstration, rehearse the existing evidence and verify health/read access. During the interview, show delivered behavior and explain the next decision. Do not launch a new write demonstration or imply a committed production roadmap.

For a pilot, establish a manual baseline and measure correctness, handling/clarification effort, failure recovery, duplicate effects and maintenance cost on the same request mix. No existing evidence quantifies time saved, ROI, adoption or customer satisfaction.
