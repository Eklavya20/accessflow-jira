# Milestone 3 bounded unattended write policy - consumed and disabled

The user explicitly approved the exact activation hash below on October 19, 2026. The background worker consumed its single authorized action on AIS-5, posting internal comment 10007. Independent reads, later polling and an actual worker restart verified one matching comment. All unattended write gates are now disabled and the healthy worker is running dry-run. The previous M1/M2 approvals were not reused; AIS-4 received no comment. Evidence is retained locally in `reports/milestone3-policy-approval.json` and passed `reports/milestone3-automatic-write.json`.

## Approved and consumed authorization

| Boundary | Approved limit |
| --- | --- |
| Site | Private sandbox origin; omitted from public copy |
| Project / service desk | AIS / 2; actual IDs verified again before writing |
| Request type | Get IT help, ID 9 only |
| Ticket | AIS-5 only, manually created after approval and worker activation |
| Summary | Must begin `TEST - AccessFlow M3` |
| Outcome | `ready_for_human_fulfillment` only; other outcomes remain dry-run |
| Operation | Append an internal triage comment using existing deterministic triage-v1 rendering |
| Visibility | `public: false` only |
| Limit | One logical comment action total; one revision per ticket; at most one action per poll |
| Expiry | October 23, 2026, 00:00 UTC (02:00 Europe/Paris) |
| Excluded | AIS-1/2/3/4 writes, all other tickets/projects/types, public comments, status/assignment/approval changes, provisioning, ticket creation |

The exact disabled sandbox policy is retained privately at `data/worker-write-policy.local.json`; local `.env` selects it with `ACCESSFLOW_WRITE_POLICY_PATH`. The public [config/worker-write-policy.json](../config/worker-write-policy.json) is now an unapproved, expired placeholder with different scope and bytes. The SHA-256 below belongs only to the original explicitly approved activation bytes (temporarily `approved: true`), not the public placeholder:

`5f8ddabbefe9c15410294cf73ff9ea6a0cb8e784618687233d11ec43159e3808`

Activation followed explicit user approval: those bytes and the hash were verified, the three private settings were enabled, and the service was restarted. Independent GET-only preflight confirmed AIS-5 was absent and preserved snapshots of AIS-1 through AIS-4. After automatic write/read-back, later poll and restart verification, the service was stopped; policy approved=false, worker enabled=false, dry-run=true and approved hash blank were restored; read-only service startup/read-back passed. The one consumed SQLite reservation remains intact. This record grants no future write action, replacement target or budget reset.

## Duplicate prevention and failures

SQLite reserves the policy budget before a remote attempt. Reservations survive restart and are not refunded after a failure or crash. The existing issue lock, operation marker, exact-body hash, and durable intent journal still apply. Fresh source and policy scope are checked before a new POST. Successful writes require separate GET verification of exact body, author and internal visibility. Uncertain outcomes reconcile by comment ID/marker without blind resend; an absent uncertain comment blocks and needs operator investigation. Definitive 400/401/403 write denials need operator review; automatic retries cannot force a new POST. The budget limits logical actions; GET retries and reconciliation do not consume new comment actions.

There is no automatic deletion or reversal of an appended Jira comment. Disable writes, retain evidence and have the account owner review any correction. This policy grants no deletion authority.

Immediate disable: edit the policy to `approved: false` (checked before each new POST), or use authenticated `POST /admin/shutdown` / `scripts/manage_service.py stop`. Then restore `ACCESSFLOW_WORKER_WRITE_ENABLED=false` and `ACCESSFLOW_DRY_RUN=true` before restarting. An already transmitted request cannot be recalled.

## Exact example - AIS-4 preview only, never authorized for posting

This is the exact example reviewed before approval, generated automatically from AIS-4. AIS-4 remained dry-run and excluded from write scope. The policy authorized the deterministic format within its limits, rather than posting this example body.

```text
AccessFlow automated triage (v1)
Application: GitHub
Access level: Read-only
Business justification: Verifying independent AccessFlow polling in the sandbox.
Outcome: Ready for human fulfillment
Reason: Required information present
Missing information: None
Action: IT support team to review and fulfill under the normal access policy.
This records triage only. Human authorization and fulfillment remain required.
[accessflow-triage:v1:e53606ab1c9b91fcf4cde8316c26c28e462b2f79caff25ecd24e56f396e08ac4]
```

Example body SHA-256: `0b92d4fb1b38b57afdb50823c1b71a6a9e8003f439f3b84f9ac8113449a911ae`.

## Completed automatic acceptance

1. Activated only the reviewed policy/settings and restarted the worker.
2. User manually created AIS-5 through Get IT help, summary `TEST - AccessFlow M3 automatic internal comment`, description:

```text
Application: GitHub
Access level: Read-only
Business justification: Verifying bounded automatic internal triage in the sandbox.

Sandbox test only. No actual access should be granted.
```

3. Worker automatically discovered, classified and wrote AIS-5; no manual process/retry command ran.
4. Independent GETs verified comment 10007's exact body, author, `public: false` and one marker match. Status/assignment matched the pre-comment audit; AIS-1 through AIS-4 snapshots were unchanged.
5. Later scheduled poll and real worker restart retained the same operation/comment and added zero POSTs. The entire worker mutation trace contains only the one AIS-5 comment POST, HTTP 201.
6. Disabled all unattended-write gates, restarted read-only and reverified the comment. SQLite operation/budget state survived restart and a backup integrity/reopen check.

## Exact posted AIS-5 internal comment 10007

```text
AccessFlow automated triage (v1)
Application: GitHub
Access level: Read-only
Business justification: Verifying bounded automatic internal triage in the sandbox.
Outcome: Ready for human fulfillment
Reason: Required information present
Missing information: None
Action: IT support team to review and fulfill under the normal access policy.
This records triage only. Human authorization and fulfillment remain required.
[accessflow-triage:v1:c321d896dd15e3f2758472eb641bde82bb1c11a9202fcb017eacfdc321193e61]
```

Body SHA-256: `75b1857fd8e0861adebadb85b35bd6e3e3aa5aa030d21214ec54f9485a4267e9`.

Any future ticket/action needs a new bounded review and explicit approval. Do not reset the consumed reservation or create/edit Jira requests through the API under this approval.
