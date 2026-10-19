"""Populate ignored local settings without putting a token in command arguments or logs."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

import httpx
from dotenv import set_key

from accessflow.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        # Validate the host before any network call. No secret is sent to tenant_info.
        site = Settings.cloud_site(args.site)
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.get(site + "/_edge/tenant_info")
            if response.status_code != 200:
                print(json.dumps({"event": "cloud_id_failed", "http_status": response.status_code}))
                return 1
            cloud_id = str(UUID(response.json()["cloudId"]))
        token = args.token_file.read_text(encoding="utf-8-sig").strip()
        if not token or any(char.isspace() for char in token):
            print(json.dumps({"event": "token_file_invalid", "reason": "Expected one token"}))
            return 1
        values = {
            "JIRA_SITE_URL": site,
            "JIRA_EMAIL": args.email,
            "JIRA_API_TOKEN": token,
            "JIRA_TOKEN_KIND": "scoped",
            "JIRA_CLOUD_ID": cloud_id,
            "JIRA_PROJECT_KEY": args.project,
            "JIRA_ALLOWED_PROJECT_KEYS": args.project,
            "JIRA_TEST_ISSUE_KEY": args.issue,
            "ACCESSFLOW_DRY_RUN": "true",
        }
        target = Path(__file__).resolve().parents[1] / ".env"
        target.touch(exist_ok=True)
        for key, value in values.items():
            set_key(target, key, value, quote_mode="always")
        print(
            json.dumps(
                {
                    "event": "local_configuration_written",
                    "cloud_id": cloud_id,
                    "token": "not_displayed",
                    "dry_run": True,
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        print(
            json.dumps({"event": "configuration_failed", "reason": "Network, file, or data error"}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
