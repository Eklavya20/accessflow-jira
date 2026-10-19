# AccessFlow interview pack

A reusable presentation guide for the verified sandbox implementation.

**Opening:** “AccessFlow prepares Jira access requests for human decisions. I implemented a working integration, proved one explicitly authorized automatic internal comment against real Jira, tested restart and duplicate prevention, and separated that evidence from production capabilities we have not validated.”

## Read and present

| Order | Material | Purpose |
| --- | --- | --- |
| 1 | [Product overview](PRODUCT_OVERVIEW.md) | One-page problem, users, value, delivered scope and limits |
| 2 | [Two-minute demo](DEMO_SCRIPT.md) | Timed narration, exact read-only commands and fallback |
| 3 | [Architecture](ARCHITECTURE.md) | Current components, data flow, authorization and failure handling |
| 4 | [Business analysis](BUSINESS_ANALYSIS.md) | Discovery, requirements, stories, acceptance, risks and planning |
| 5 | [Interview Q&A](INTERVIEW_QA.md) | Technical and product reasoning, including build versus native automation |
| 6 | [Final verification](FINAL_VERIFICATION.md) | Implemented, offline-tested, live-verified and untested capabilities |
| 7 | [Code review](CODE_REVIEW.md) | Narrow fixes, regression evidence and residual risks |

Keep [measured results](RESULTS.md), the [runbook](RUNBOOK.md), and the [consumed AIS-5 policy](MILESTONE3_WRITE_POLICY.md) available for follow-up.

## Demonstration contract

Use existing AIS-5/comment **10007**, AIS-1 privileged review, AIS-3 missing information and AIS-4 dry-run evidence. Do not create a request, run `process`, schedule a retry, replay a write verifier, or re-enable the consumed policy during the interview. The current service polls in dry-run; a green health response demonstrates operation, while the existing Jira comment/audit demonstrates the historical authorized write.

Close credential files and disable any screen sharing of environment values, private reports, database contents or full terminal history. Synthetic request details may be shown deliberately; local evidence can still contain private account/project metadata. Keep account-specific presentation material private.

## Rehearsal

- Before the interview: run the read-only preflight in the demo, pre-open the Jira tabs, and keep the local evidence fallback ready.
- Rehearse the spoken script once to a two-minute timer. Have evidence already loaded; do not wait through a polling interval on screen.
- If a check fails, describe the observed limitation and use the dated evidence. Do not repair credentials or enable writes during the presentation.
- Close on the next product decision: whether simple native automation meets the need, or the additional control and maintenance of a Python service is justified.

Claim measured execution and explicit trade-offs. Do not claim measured time savings, customer adoption, security certification, distributed exactly-once delivery or production readiness.
