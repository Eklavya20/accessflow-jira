# Milestone 2 acceptance tickets and write review

Status: **Milestone 2 passes.** All three real cases were classified, explicitly approved internal comments were created/read back as 10004/10005/10006, and same-process/fresh-process repeats added no duplicates. Current offline suite: 127 passed. Exact approved bodies/hashes and scope are in [the write review](MILESTONE2_WRITE_REVIEW.md); measured evidence is in [RESULTS.md](RESULTS.md). Milestone 1 comment 10003 is preserved as a separate operation.

## Create two synthetic portal requests

The user created AIS-2 and AIS-3 in the AIS portal using the existing **Get IT help** request type. The exact original descriptions below document the acceptance inputs. AIS-1 uses Request admin access. No ticket-creation API call was attempted or authorized; creation was manual.

### Standard access case

Summary:

```text
TEST - GitHub read-only access for documentation review
```

Exact description:

```text
Application: GitHub
Access level: Read-only
Business justification: Reviewing project documentation for the AccessFlow sandbox.

Sandbox test only. No actual access should be granted.
```

Expected outcome: `ready_for_human_fulfillment`; internal triage comment asks the IT support team to review and fulfill under normal policy. This is a preparation outcome, not a grant or Jira status transition.

### Incomplete access case

Summary:

```text
TEST - Incomplete GitHub access request
```

Exact description:

```text
Application: GitHub
I need GitHub access.

Sandbox test only. No actual access should be granted.
```

Expected outcome: `needs_information`; missing Access level and Business justification. The proposed internal comment instructs IT to ask the requester for those details. It does not notify the customer through a public comment.

## Authorized write scope

The user explicitly approved the three exact reviewed triage bodies and hashes, separately from the earlier Milestone 1 connectivity comment. All three were posted with `public: false` and a versioned stable marker. No status, assignment, approval-decision or external-permission write was sent. Any additional triage comment requires new authorization.

Read-only dry-run and explicitly approved write acceptance passed on all three tickets. Exact comment hashes matched fresh computed plans before posting. Changed input still requires a fresh dry-run and approval; the three-comment approval is not a general operating policy. No automatic ticket creation, public comments, field edits or transitions are included.

## AIS-1 exact reviewed body — posted as internal comment 10004

Visibility: **internal only** (`public: false`). Exact body:

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

SHA-256: `67e604786af91401977dcf32595bbd94b50503a45bc99c3bc04bf5935047850a`.

This body was explicitly approved, posted and verified. The full set of three bodies is preserved in [the write review](MILESTONE2_WRITE_REVIEW.md). If input/policy changes, rerun the dry-run and review the new body/hash before any new write.

## Completed live evidence

1. Separate Jira GETs verified one exact internal triage comment per approved request, including body and author.
2. Same-process and new-process repeats with the same SQLite database returned identical comment IDs and sent zero further POSTs.
3. Separate `show` and `audit` processes recovered durable classifications and successful action history.
4. Status and assignment fingerprints were unchanged; counts and the HTTP trace confirmed exactly three authorized comment writes.

Unknown/ambiguous inputs, updated input, API failure, crash recovery, and concurrency are covered offline; do not claim those cases were exercised live without additional controlled evidence.
