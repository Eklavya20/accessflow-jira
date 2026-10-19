# Public repository preparation

Prepared October 19-20, 2026. This repository is prepared for a public engineering portfolio; the sandbox verification does not establish production readiness.

## Publication content

- MIT licensing is recorded in `LICENSE` and package metadata.
- Personal sandbox origins, machine paths and interviewer-specific context have been removed from public documents/configuration. Synthetic AIS case identifiers, exact approved comment bodies, historical hashes and measured results remain for traceability.
- The exact disabled sandbox policy remains at ignored `data/worker-write-policy.local.json`, selected by private `.env`. The public policy is an unapproved, expired placeholder; its bytes do not match the consumed historical activation hash.
- Original account-specific documents remain privately under ignored `reports/publication-originals/`. Databases, raw reports/logs and credential files remain local.
- `.gitattributes` normalizes source/document line endings. Docker's build allowlist and copy instructions include the new license; Docker/Compose remains unverified.

## Verification

The local Git index is inspected before the first commit. Publication evidence is retained privately at `reports/publication-audit.json`; staged source files and reachable local Git history are checked for known local credentials and account identifiers without recording the secret values. Ignore checks cover the real local credential/state/report files and representative SQLite/log variants. This is a scoped local check, not a certification or a scan of other repository copies.

The offline verification command is `python scripts/check.py`. It runs pytest, Ruff lint/format and `pip check`, without invoking any live acceptance scripts. The GitHub Actions workflow uses Windows/Python 3.11, locked dependencies, read-only repository permissions and commit-pinned official actions. It receives no Jira secrets, starts no worker, and does not upload local reports. Official action references: [checkout v6.0.2](https://github.com/actions/checkout/releases/tag/v6.0.2), [setup-python v6.2.0](https://github.com/actions/setup-python/releases/tag/v6.2.0).

Local results:

| Check | Observed result |
| --- | --- |
| Actual Git staging area | 71 public files; no known local credential/account literals or credential-pattern matches |
| Ignore engine | 43 private path cases excluded; five intended public paths retained (including the expanded backup patterns) |
| Source-only snapshot | Exported from the index with no `.env`, token files or historical database; fresh virtual environment installed locked dependencies and the package, then passed 186 tests with zero failures/errors/skips |
| Lint / format / dependencies | Passed; all 36 Python files formatted; one existing Starlette/AnyIO deprecation warning in the snapshot run |
| Package build | Wheel built offline with installed build tools; MIT license included; Docker not exercised |
| Hosted CI | Initial release `4146c23` passed [GitHub Actions run 39332809467](https://github.com/Eklavya20/accessflow-jira/actions/runs/39332809467) on Windows/Python 3.11; logs confirm 186 tests, lint, formatting and dependency checks passed |
| Documentation / diff | Relative links resolve; staged whitespace check passes |
| Configuration authority | Effective local settings: dry-run true, worker write false, activation hash blank; private and public policies unapproved |
| Local runtime observation | Health connection refused during publication checks; no current running-service claim is made. Preparation did not start/stop a worker or call Jira |

The first snapshot check used the existing dependency environment. The October 20 check additionally installed locked dependencies and the editable package into a fresh virtual environment from the source-only export; all checks passed. The documented `.env.example` configuration and admin-token generation were verified offline with synthetic non-AIS identifiers. The first hosted GitHub Actions run independently installed and verified the initial release; its successful steps and logs were checked through the GitHub API. Neither local nor hosted offline checks establish live Jira acceptance or Docker runtime behavior. The check runner uses a unique temporary directory under ignored `reports/`, avoiding stale Windows permissions left by a previous run/account.

## First publication

The initial preparation initialized local branch `main` and audited the reviewed staging area before any commit. On October 20 the owner supplied the public destination [Eklavya20/accessflow-jira](https://github.com/Eklavya20/accessflow-jira), verified empty before publication. Initial release `4146c23` was pushed after the renewed credential, reachable-history and reproducibility checks passed. GitHub's branch, file tree and README matched the audited local commit. Commit identity uses the owner's GitHub noreply address, rather than a work email. Current detailed execution evidence remains private under `reports/`.

The README now contains a compact product explanation and architecture diagram, fresh-clone installation, the verified evidence and its limits. Setup instructions use each developer's discovered identifiers, not the historical sandbox IDs. Loose token files have been moved into restricted Windows LocalAppData storage outside the checkout. The existing ignored `.env` remains the local runtime credential source; its contents are not removed by moving the loose files. Backup directories and common backup/dump file patterns are excluded as well.

Inspect `git diff --cached --stat` and `git status --short` before future commits; never force-add `.env`, credentials, `data/` or `reports/`. Raw reports, logs and databases are deliberately not public evidence artifacts. The public documents retain synthetic case identifiers and historical comment/hash evidence, with account-specific origins omitted.

For a fresh clone, install the locked development environment and package as shown in the README, then run the offline checks before configuring Jira. Local `.env`, historical SQLite state and raw evidence are deliberately absent from a clone. Historic acceptance verifier scripts are retained for traceability; they are not CI/setup commands and must not be replayed against Jira without fresh explicit authorization.

Unattended write gates remain disabled. Publication preparation does not authorize any Jira modification.
