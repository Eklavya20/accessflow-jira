# Two-minute interview demonstration

Use existing verified evidence only. Unattended writes are disabled; no request creation, manual processing or write replay belongs in this demonstration.

## Timed spoken script

**0:00-0:20 - Problem and users.** "IT agents repeatedly check an application's requested access level and justification, then choose a human next step. AccessFlow prepares that triage consistently. Support agents get a usable summary; application owners still authorize access and humans fulfill it."

**0:20-0:45 - Real execution.** Show existing AIS-5/comment 10007 and its historical worker log. "I created AIS-5 through the Jira portal. The worker found it without a processing command, classified GitHub Read-only and posted this one authorized internal comment. A separate API read verified its exact body, author and internal visibility. This was actual Jira execution."

**0:45-1:05 - Requirements and boundaries.** Show AIS-1 privileged and AIS-3 incomplete summaries. "These cases require human review or missing information. AIS-4 first proved automatic dry-run. AIS-5 then used a separately approved one-action policy. Its budget is consumed and writes are disabled. No status, assignment, approval or application permission was changed."

**1:05-1:30 - Reliability.** Show the architecture, health and selected audit. "One worker polls every 60 seconds. SQLite keeps checkpoints, action intentions and audit history. A later poll and a real worker restart retained comment 10007 with zero additional POSTs. Uncertain writes reconcile rather than resend. The final 186 offline tests include failures and rate limits; live outage recovery remains untested."

**1:30-1:45 - Trade-offs.** "For simple Jira rules, I would evaluate native automation first. Python gives explicit tested policy and reconciliation, with a possible future cross-system role, but adds hosting responsibility. Native Windows startup was tested; Docker Compose remains unverified."

**1:45-2:00 - Product decision.** Show [final verification](FINAL_VERIFICATION.md). "This proves working integration and controlled execution. Next I would validate the pilot need, operational ownership, deployment and recovery before expanding scope. Time savings, production adoption and ROI have not been measured."

Rehearse to a timer; keep evidence loaded rather than waiting through a polling interval. This is a demonstration of an existing real execution, not a new write test.

## Read-only preflight and screen setup

From the repository root in PowerShell, before screen sharing:

```powershell
.\.venv\Scripts\python.exe scripts/manage_service.py health
.\.venv\Scripts\python.exe -m accessflow show AIS-5
.\.venv\Scripts\python.exe -m accessflow audit AIS-5 --limit 20
```

These commands read health/local state, not process tickets. `show` may report `mode: dry_run` after the deliberate return to read-only operation; `write_status: verified` and `comment_id: 10007` refer to the retained remote effect. Use the historical `comment_created_and_verified` audit to explain the write.

The links below use a placeholder site; use the private `JIRA_SITE_URL` locally to open the existing tickets. Original account-specific demo notes are retained under ignored `reports/publication-originals/`. Pre-open [AIS-5](https://your-site.atlassian.net/browse/AIS-5), [AIS-1](https://your-site.atlassian.net/browse/AIS-1) and [AIS-3](https://your-site.atlassian.net/browse/AIS-3) in the authenticated sandbox. On AIS-5, show existing comment 10007 and its internal visibility. AIS-2 is the earlier standard case; AIS-4 is the automatic dry-run control. No browser UI screenshot is claimed in the verification report.

Select the historical automatic completion line without exposing the whole log:

```powershell
Get-Content reports/native-service.stderr.log |
  Where-Object { $_ -match '"issue_key": "AIS-5"' -and $_ -match '"mode": "write"' } |
  Select-Object -First 1
```

If the service is stopped, use the [runbook](RUNBOOK.md) startup command before rehearsal and wait for its own successful poll. An initial 503 is expected, including any persisted rate-limit wait. Do not restart, process, retry, run write-verification scripts or change configuration during the presentation.

## Fallback and evidence limits

If Jira/network access fails, say so and use the dated [results](RESULTS.md), [exact posted body/policy record](MILESTONE3_WRITE_POLICY.md) and local `show`/`audit` output. Those are retained evidence, not a fresh live success. Never open `jiratoken.txt`, `.env`, full private reports or database tables on screen.

| Existing case | What to show |
| --- | --- |
| AIS-5 / comment 10007 | Automatic standard-case internal write; primary demonstration |
| AIS-1 / comment 10004 | Privileged access routed to human review |
| AIS-3 / comment 10006 | Access level and justification missing |
| AIS-4 / no comment | Automatic dry-run control |
| AIS-2 / comment 10005 | Earlier standard case, if follow-up detail is useful |
