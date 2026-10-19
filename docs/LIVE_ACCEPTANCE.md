# Live Jira acceptance procedure

Status: MILESTONE 1 PASSED. The v2 token passes identity and Platform/JSM reads. The approved internal comment is 10003; read-back, same-process repeat, fresh-process repeat, and one-comment count passed. The later workflow acceptance suite has not been executed. See [results](RESULTS.md). Run only against designated synthetic requests in the configured test service project. Keep token values and personal/customer information out of reports and screenshots.

## Milestone 1: establish real connectivity

1. Complete [Jira setup](JIRA_SETUP.md). Record date, actual site/project/desk IDs, project type, subscription, identity role, and token kind in a local private report. Record no token.
2. Run `python -m accessflow discover` using the repository virtual environment. Confirm real project/desk metadata and required request fields.
3. Run `python -m accessflow check`. Confirm the designated issue's actual project and service desk, stable issue ID, and `BROWSE_PROJECTS`/`ADD_COMMENTS`. Inspect optional capability failures and record the precise HTTP status; do not infer plan restrictions from a 403 alone.
4. Keep `ACCESSFLOW_DRY_RUN=true`. Preview the exact harmless comment and intended visibility:

   ```powershell
   .\.venv\Scripts\python.exe -m accessflow probe-comment --confirm AFTEST-1 --visibility internal
   ```

   Replace `AFTEST-1` with your configured test issue. Confirm output says `mode: dry_run`, `write: not_attempted`, and `public: false`. Public visibility is an explicit alternative requiring its own user approval and may notify customers.

5. Ask the account owner to explicitly approve the exact issue, visibility, and displayed comment. **This separate confirmation is required by the project brief.** The agent must not treat a general instruction to build AccessFlow as permission to run this write.
6. Only after approval, set `ACCESSFLOW_DRY_RUN=false` locally and run the same command. It reserves a durable journal row, performs one POST, then retrieves the comment by ID. Success requires `write: created_and_verified` and inspection in Jira with the intended visibility. If denied, stop and diagnose; do not switch visibility automatically.
7. Start a new CLI process and run the same command again. Expect `already_verified` with the same comment ID; count matching comments in Jira to confirm one. If a prior POST was uncertain, expect `reconciled` when its comment becomes visible; an absent comment leaves the operation blocked rather than resending.
8. Restore `ACCESSFLOW_DRY_RUN=true`. Record actual timestamps, issue/comment IDs, read-back result, test operator, and limitations in a private report. Update `RESULTS.md` with a sanitized summary. The utility does not automatically declare Milestone 1 complete.

## Later workflow acceptance (blocked until MVP implementation)

Milestone 2 passed through `process`, `show`, `audit`, and `retry`: privileged AIS-1, standard AIS-2 and incomplete AIS-3 were classified, and approved internal comments 10004/10005/10006 were read back without repeat POSTs. Milestone 3 then passed autonomous AIS-4 dry-run, separately approved automatic AIS-5 comment 10007, independent read-back, later-poll and actual native worker-restart checks. Writes are disabled again. See [measured results](RESULTS.md), [current acceptance](MILESTONE3_ACCEPTANCE.md) and [the consumed policy record](MILESTONE3_WRITE_POLICY.md). The broader table below includes outstanding production deployment/failure criteria; offline tests cannot pass those live gates.

| Criterion | Procedure | Pass condition |
| --- | --- | --- |
| 1. Authentication | Active identity GET | Real account authenticated |
| 2. Real request read | Designated JSM request GET | Stable ID and actual project/desk match |
| 3. Verified write | Approved connectivity comment above | POST plus separate GET/UI verification |
| 4. Complete request | GitHub, read-only, documentation justification | Configured human route applied and audited |
| 5. Incomplete request | "Please give me GitHub access" | One clear comment asking for access level/justification; waiting transition only if configured |
| 6. Privileged request | GitHub administrator with migration justification | Sensitive flag and authorized reviewer; no access grant; native decision observed only if actually configured |
| 7. Duplicate prevention | Process each ticket twice and after a fresh process start | No extra clarification or repeated transition; persistent action records |
| 8. API failure | Temporarily block the worker's route to real Jira in a controlled local test, restore it, then inspect recovery | Durable failure, bounded retries, no duplicated effects, eventual recovery or visible operator action |
| 9. Restart | Stop/restart worker with SQLite state retained | Prior outcomes remain; safe resumed processing |
| 10. Reproducible operation | Build/run documented local Compose deployment with editor closed | Health/admin controls, worker, volumes, runbook work as documented |

For criterion 8, do not overload Atlassian or change global workstation networking. Select an isolated process/container method when the worker exists. Offline httpx fault tests separately exercise exact 401/403/429/5xx semantics; record honestly if a live rate-limit response was never observed. A test stub cannot be used as proof of live Jira acceptance.

Additional checks: add a real customer reply with missing fields and verify reevaluation; send an unknown application and verify human review; reject an issue outside the configured test project without writing; inspect public/internal visibility using appropriate customer/agent views. Verify genuine native approval via an authorized human's workflow action if supported. A comment with "approved" must never satisfy authorization.

## Evidence record template

Keep raw reports locally under ignored `reports/`. For each case record: observed time, configured test scope, actual issue ID/key, input scenario, relevant pre-state, command/version, intended action, actual comment/transition/field result, audit reference, elapsed time, repeat-run count, pass/fail, and limitations. Sanitize any material used in the interview.

If native approvals, a waiting transition, or editable routing fields are unavailable, record that exact limitation and agree a smaller real human-review route before executing revised acceptance. Do not call manual review a native approval.
