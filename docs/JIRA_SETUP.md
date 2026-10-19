# Jira setup and configuration

Configure your own dedicated Jira Service Management Cloud sandbox. The historical AIS acceptance environment is documented in [results](RESULTS.md); its project, service-desk and request-type IDs are not defaults for another site. No paid resources or subscriptions have been created by AccessFlow.

## 1. Establish a sandbox

If you already have JSM Cloud, use a dedicated test service project containing synthetic data. Otherwise, sign into Atlassian and select an available Free Jira Service Management/Service Collection option. Confirm the displayed plan and any trial expiration before proceeding; do not purchase a plan for this project. Create a service-management project, record its project key, and ensure your account can work as an agent in it. Product navigation may use the term service space.

Create one request through that project's customer portal using an existing request type. Use a synthetic example such as:

```text
Application: GitHub
Access level: Read-only
Business justification: Review documentation for the AccessFlow sandbox
```

Record the resulting canonical issue key. A plain Jira software issue without a JSM request type is insufficient. Do not configure real application provisioning or use real employee records.

## 2. Configure authentication locally

Copy `.env.example` to `.env` if it does not exist. Edit locally in VS Code. The utility reads `.env` in the current working directory, with environment variables taking precedence. Keep the file outside shared screenshots, version control, and demo materials; restrict access to your Windows user. `.gitignore` excludes local secrets and state but does not encrypt them.

Keep loose token files outside the checkout, for example in a restricted folder under your Windows LocalAppData directory. The application reads `JIRA_API_TOKEN` from the process environment or private `.env`; it does not automatically read an external token file. Moving a loose file does not remove the runtime credential from `.env`. Managed secret storage and rotation remain deployment work.

Create a short-lived token in [Atlassian API token settings](https://id.atlassian.com/manage-profile/security/api-tokens). Use the email of the account that owns the token, never an account password. Atlassian recommends scoped tokens; these use the gateway URL and require a cloud ID. See [Atlassian token instructions](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

| Variable | Required value |
| --- | --- |
| `JIRA_SITE_URL` | Site origin, e.g. `https://your-site.atlassian.net`, without a path |
| `JIRA_EMAIL` | Token owner's Atlassian account email |
| `JIRA_API_TOKEN` | Token stored only locally |
| `JIRA_TOKEN_KIND` | `scoped` or `unscoped`, matching how the token was created |
| `JIRA_CLOUD_ID` | UUID for scoped tokens; unused for unscoped tokens |
| `ACCESSFLOW_DRY_RUN` | Keep `true` for discovery and the first comment preview |

For the cloud ID, inspect `https://YOUR-SITE.atlassian.net/_edge/tenant_info` in your browser and copy `cloudId`; [Atlassian documents this method](https://support.atlassian.com/jira/kb/retrieve-my-atlassian-sites-cloud-id/). Never guess it. Scoped tokens use `https://api.atlassian.com/ex/jira/{cloudId}`; unscoped tokens use the configured site origin. The utility constructs those URLs and disables redirects.

For a scoped token, the API references list classic read scopes `read:jira-user`, `read:jira-work`, and `read:servicedesk-request` for these discovery operations; the comment probe needs `write:servicedesk-request`. If your token UI exposes granular scopes, use the endpoint-specific scope lists in the [API references](JIRA_FEASIBILITY.md); token scope and account permission must both allow each operation. Do not grant admin scopes to work around a denied request. OAuth is not implemented in this initial personal utility; assess it before wider organizational adoption.

## 3. Discover identifiers

```powershell
.\.venv\Scripts\python.exe -m accessflow discover
```

Read `projects` and `service_desks`. Initial discovery does not need target identifiers. Set these from actual returned metadata:

| Variable | Value |
| --- | --- |
| `JIRA_PROJECT_KEY` | Dedicated test project key |
| `JIRA_PROJECT_ID` | Numeric project ID |
| `JIRA_SERVICE_DESK_ID` | Numeric service desk ID for that same project; not the project ID |
| `JIRA_ALLOWED_PROJECT_KEYS` | Only the test project key for now; comma-separated syntax is supported |
| `JIRA_TEST_ISSUE_KEY` | Designated synthetic portal request's issue key |

Run `discover` again to list that desk's request types and required fields, then:

```powershell
.\.venv\Scripts\python.exe -m accessflow check
```

This verifies live identity, actual issue project membership and desk ownership. `BROWSE_PROJECTS` and `ADD_COMMENTS` are needed for the connectivity comment. Later routing will also require the applicable edit, transition, or assignment permission, with available fields and transitions confirmed on the actual issue. An agent identity is needed to test internal comments; the utility never falls back to public visibility on failure.

## 4. Configure the polling worker

Set `ACCESSFLOW_REQUEST_TYPE_IDS` to the comma-separated numeric request-type IDs returned by discovery for your allowlisted desk. Do not copy the historical AIS IDs. The worker additionally requires a private `ACCESSFLOW_ADMIN_TOKEN` of at least 32 characters; generate one locally without printing it or overwriting an existing value:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; from dotenv import dotenv_values, set_key; dotenv_values('.env').get('ACCESSFLOW_ADMIN_TOKEN') or set_key('.env', 'ACCESSFLOW_ADMIN_TOKEN', secrets.token_urlsafe(32))"
```

Keep `ACCESSFLOW_DRY_RUN=true`, `ACCESSFLOW_WORKER_WRITE_ENABLED=false` and `ACCESSFLOW_APPROVED_POLICY_SHA256` blank. The public worker policy is disabled and expired; it grants no authority. Default polling is 60 seconds, with a full source rescan every 300 seconds. SQLite initializes automatically under ignored `data/` when processing starts.

Start and observe the worker using the [native runbook](RUNBOOK.md). Initial health returns 503 until the current run completes its first successful poll. A successful setup/configuration check does not constitute a new live integration acceptance test.

## 5. Confirm the plan and human review mechanism

Record your actual subscription, project type, existing workflow states, agent access, and whether a request with a real approval step can be created. An approval API returning an empty list does not establish plan entitlement or workflow configuration. See [approval differences](https://support.atlassian.com/jira-service-management-cloud/docs/what-are-the-differences-in-classic-and-next-gen-approvals/) and [Free plan permission limitations](https://confluence.atlassian.com/servicedeskcloud/project-permissions-roles-and-issue-level-security-in-free-plans-1097175961.html).

If native approvals are unavailable, select a real, permitted human-review workflow using the observed labels, assignment, or statuses. Document the reviewer and escalation owner. A comment saying "approved" cannot authorize access. No upgrade or custom field is assumed necessary.

Proceed to the [live acceptance procedure](LIVE_ACCEPTANCE.md) only after read discovery succeeds. The user must explicitly approve the exact connectivity-comment ticket and visibility before the agent runs a write.

## Other settings

`DATABASE_URL` supports file-backed SQLite for processing, worker state and audit; its default is `sqlite:///data/accessflow.db`. `JIRA_READ_ATTEMPTS`, `JIRA_TIMEOUT_SECONDS`, and `JIRA_MAX_RETRY_WAIT_SECONDS` bound read recovery. A `Retry-After` longer than the local wait budget stops a CLI read without an early retry; the worker retains retry deadlines across restarts. CLI lifecycle/error events emit JSON. No LLM dependency or call exists.

`ACCESSFLOW_PROBE_COMMENT_BODY` optionally supplies an exact operator-approved comment, with no marker appended. Its hash is bound to the durable operation so changing the text cannot create another comment. A blank setting preserves the original marked default. `JIRA_QUERY_APPROVALS=false` skips native-approval queries unless workflow configuration and the endpoint's read scopes have been confirmed.

For a user-supplied local token file, `scripts/configure_jira.py` accepts site/email/project/issue and token-file arguments, discovers the public Cloud ID, and populates the ignored `.env` without printing the token. It resets dry-run to true. Run it only after excluding the token file and checking available Git tracking/history. `scripts/live_read.py --skip-identity` supports targeted read-only diagnostics when identity access is already known to be denied; it never writes Jira data and saves a redacted local report. The normal `accessflow check` retains its strict identity and target validation.
