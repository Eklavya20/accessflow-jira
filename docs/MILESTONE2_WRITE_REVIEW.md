# Milestone 2 approved internal comments and verification

Live dry-run review and explicitly authorized write acceptance completed October 19, 2026. **The exact bodies below were posted and verified:** AIS-1 comment `10004`, AIS-2 comment `10005`, AIS-3 comment `10006`. Each is internal (`public: false`). Statuses and assignments are unchanged; no approval-decision, other-ticket or external-permission mutation was sent. Same-process and fresh-process repeats sent no POSTs.

| Ticket | Stable ID | Live outcome | Approved comment SHA-256 |
| --- | --- | --- | --- |
| AIS-1 | 10006 | Privileged human review | `67e604786af91401977dcf32595bbd94b50503a45bc99c3bc04bf5935047850a` |
| AIS-2 | 10007 | Ready for human fulfillment | `a4df22633205300321ab6e178fa4ca18b2c04e328df6f1902689a2bec2de5408` |
| AIS-3 | 10008 | Missing information | `dd25763d9af360ac1a133616f4d7454b895516add18d6c8a7c3daa60bd590c14` |

All three are revision 1, Waiting for support, and report Browse Projects/Add Comments permission. Before writing, exact proposed-body/marker matches were zero on every ticket. After all checks there is exactly one triage match per ticket. Total comments are 2 on AIS-1 (including its preserved M1 connectivity comment), 1 on AIS-2, and 1 on AIS-3.

## AIS-1 — internal

```text
AccessFlow automated triage (v1)
Application: Demo Analytics
Access level: Administrator
Business justification: Testing the AccessFlow access-request validation and human approval workflow.
Outcome: Privileged access - human review required
Reason: Privileged access requires explicit human review
Missing information: None
Action: Authorized application owner or security reviewer to review authorization before any fulfillment.
This records triage only. Human authorization and fulfillment remain required.
[accessflow-triage:v1:af63f599d2da61930d35328bd9267f3dfddd8ff93003341f39394f593688043d]
```

## AIS-2 — internal

```text
AccessFlow automated triage (v1)
Application: GitHub
Access level: Read-only
Business justification: Reviewing project documentation for the AccessFlow sandbox.
Outcome: Ready for human fulfillment
Reason: Required information present
Missing information: None
Action: IT support team to review and fulfill under the normal access policy.
This records triage only. Human authorization and fulfillment remain required.
[accessflow-triage:v1:df25765633ce73799c388de078608bb8700d902e2442de07dff2b3dcf2f85956]
```

## AIS-3 — internal

```text
AccessFlow automated triage (v1)
Application: GitHub
Access level: Not provided
Business justification: Not provided
Outcome: Missing information
Reason: Missing: Access level, Business justification
Missing information: Access level, Business justification
Action: IT support team to ask the requester for: Access level, Business justification.
This records triage only. Human authorization and fulfillment remain required.
[accessflow-triage:v1:7a931ade1ccf3c049738fcc2178d6505a58dc2e5e5d9f15b9e30497fb011334f]
```

The SHA-256 covers the exact UTF-8 body with no trailing newline. Operation markers are part of the comment, for durable reconciliation. Exact local exports, original proposal manifest, explicit approval record and completed live evidence are under ignored `reports/`. If input or policy changes, the processor must recompute and reject a stale approval hash rather than post changed text.

## Evidence and passed gate

The earlier preview/preflight trace contained 34 GET responses and no mutation; an earlier local script quoting error stopped another attempt after two GETs and no write. After explicit approval, `scripts/verify_milestone2.py` refreshed all three plans before posting. The live acceptance trace captured exactly 3 POSTs (all HTTP 201), exact body/author/internal read-back, and 0 POSTs across six repeat executions. SQLite has verified operations and the same comment IDs after restart. Current offline evidence is 127 passing tests, including 12 verifier-scope boundary tests.

**Milestone 2 passes** within this three-ticket CLI/comment scope. Its approval covers only these bodies/hashes and grants no additional comments or general operating authority. Milestone 3 later introduced the automatic worker under separate instructions and a separately approved single AIS-5 write policy, now consumed and disabled. Public comments, transitions, assignments, approval decisions and provisioning remain excluded. See [RESULTS.md](RESULTS.md) for actual counts, times and limits.
