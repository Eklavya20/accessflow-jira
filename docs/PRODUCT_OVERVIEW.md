# AccessFlow product overview

## Problem and users

IT agents repeatedly read application-access requests to identify the application, access level and business justification, find missing information, and decide who should review sensitive access. Inconsistent preparation can create extra clarification and review work. The existence of that workload is the project hypothesis; its volume and cost have not been measured in an organization.

Employees need clear next steps. IT support needs consistent preparation and visible failures. Application owners/security reviewers retain authorization decisions. An operator needs credentials, audit history and a safe recovery path.

## Delivered workflow

AccessFlow is a working Python service connected to a real Jira Service Management Cloud sandbox. One worker polls the allowlisted AIS project/request types every 60 seconds, validates actual project/desk identity, and uses deterministic rules to classify requests as ready for human fulfillment, missing information, privileged review or manual triage. SQLite stores source checkpoints, revisions, results, retries, action intentions and audit events. A local authenticated FastAPI interface exposes status, audit and safe retry controls.

Write-back is an internal triage comment. It requires explicit, separate authority. A bounded policy allowed one automatic AIS-5 comment; it was consumed and then disabled. The healthy native Windows process now continues in dry-run. Humans still contact the requester, decide access and fulfill it; no application permissions, Jira statuses, assignments or approval decisions are changed automatically.

## Evidence and business value

| Demonstrated | Evidence |
| --- | --- |
| Real automatic discovery/classification | AIS-4 dry-run and AIS-5 approved automatic write |
| Real internal write/read-back | AIS-5 comment 10007; exact body/author/internal visibility verified |
| Duplicate prevention and persistence | Later scheduled poll and actual worker restart added zero POSTs; SQLite retained the same operation/comment |
| Engineering verification | Original 177 offline tests preserved; final review suite 186 passing |
| Independent operation | Hidden detached Windows startup, shutdown, logs, health and restart tested |

The implemented benefit is automatic preparation of a consistent, traceable next-action summary. Reduced handling time and fewer clarification cycles are hypotheses. A pilot would measure classification accuracy, manual corrections, clarification cycles, operator effort and recovery rate before claiming savings or ROI.

## Product choice and limits

For simple rules within Jira, evaluate native Jira Automation first to avoid hosting another service. Python adds explicit testable policy, durable reconciliation and a foundation for future cross-system coordination, at the cost of runtime, credentials and maintenance ownership. No external provisioning integration is implemented.

This is a verified sandbox delivery with a narrow write scope. Docker/Compose is supplied but unverified because Docker was unavailable. The native host/session must remain available; reboot supervision, production identity/RBAC/TLS, workload testing, live outage/crash drills, full deployment restore, retention and operational ownership remain rollout gates. There is no production usage, certification or measured labor saving.
