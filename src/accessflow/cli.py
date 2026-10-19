import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime

from pydantic import ValidationError

from accessflow.config import SafetyError, Settings
from accessflow.discovery import discover
from accessflow.jira import JiraClient, JiraError
from accessflow.persistence import Store
from accessflow.probe import probe_comment
from accessflow.processor import process


def emit(event: str, **details) -> None:
    print(
        json.dumps({"timestamp": datetime.now(UTC).isoformat(), "event": event, **details}),
        file=sys.stderr,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AccessFlow Jira discovery and request triage")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover", help="Read accessible project/service-desk metadata")
    sub.add_parser("check", help="Read the designated test request and probe capabilities")
    sub.add_parser("serve", help="Run the authenticated local API and polling worker")
    sub.add_parser("worker-once", help="Run one discovery/classification cycle; dry-run by default")
    sub.add_parser("worker-status", help="Read persistent worker status and job summaries")
    worker_retry = sub.add_parser("worker-retry", help="Schedule an existing failed job safely")
    worker_retry.add_argument("issue_key")
    probe = sub.add_parser("probe-comment", help="Plan or write ONE explicit connectivity comment")
    probe.add_argument(
        "--confirm",
        required=True,
        metavar="ISSUE-KEY",
        help="Explicit authorization for the designated sandbox issue",
    )
    probe.add_argument("--visibility", required=True, choices=["internal", "public"])
    for command in ("process", "retry"):
        triage = sub.add_parser(command, help="Classify one issue; default is durable dry-run")
        triage.add_argument("issue_key")
        modes = triage.add_mutually_exclusive_group()
        modes.add_argument("--dry-run", action="store_true")
        modes.add_argument(
            "--write", action="store_true", help="Enable internal write-back for this run"
        )
        triage.add_argument(
            "--approve-comment-sha256", help="Approval of the exact dry-run comment"
        )
    for command in ("show", "audit"):
        local = sub.add_parser(
            command, help="Read local durable processing evidence; no Jira calls"
        )
        local.add_argument("issue_key")
        if command == "audit":
            local.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        if args.command == "serve":
            from accessflow.service import serve

            serve(settings)
            return 0
        if args.command in ("worker-once", "worker-status", "worker-retry"):
            from accessflow.persistence import issue_lock
            from accessflow.worker import Worker, retry_job
            from accessflow.worker_store import WorkerStore

            if args.command == "worker-once":
                with issue_lock(settings.database_path(), settings.jira_site_url, "polling-worker"):
                    with JiraClient(settings) as client:
                        Worker(settings).poll(client)
            elif args.command == "worker-retry":
                result = retry_job(settings, args.issue_key)
            if args.command != "worker-retry":
                with WorkerStore(settings.database_path()) as store:
                    result = store.overview(settings.jira_site_url)
        elif args.command in ("show", "audit"):
            settings.assert_issue_key(args.issue_key)
            if args.command == "audit" and not 1 <= args.limit <= 1000:
                raise SafetyError("Audit limit must be between 1 and 1000")
            with Store(settings.database_path()) as store:
                result = (
                    store.latest(settings.jira_site_url, args.issue_key)
                    if args.command == "show"
                    else store.history(settings.jira_site_url, args.issue_key, args.limit)
                )
        else:
            with JiraClient(settings) as client:
                if args.command in ("process", "retry"):
                    result = process(
                        client,
                        args.issue_key,
                        write=args.write,
                        approved_sha256=args.approve_comment_sha256,
                        retry=args.command == "retry",
                    ).model_dump()
                elif args.command == "probe-comment":
                    result = probe_comment(
                        client, confirmed_key=args.confirm, public=args.visibility == "public"
                    )
                else:
                    result = discover(client, check_target=args.command == "check")
        print(json.dumps(result, indent=2))
        emit("command_completed", command=args.command)
        return 0
    except ValidationError as exc:
        # Pydantic's default exception text can contain secret input values.
        fields = sorted(
            {
                ".".join(map(str, error["loc"])) or "configuration"
                for error in exc.errors(include_input=False, include_context=False)
            }
        )
        emit(
            "configuration_invalid",
            fields=fields,
            action="Configure local .env using .env.example; do not share tokens",
        )
        return 2
    except (SafetyError, JiraError) as exc:
        emit(
            "command_blocked",
            command=args.command,
            reason=str(exc),
            http_status=getattr(exc, "status", None),
        )
        return 1
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError):
        # Raw OS/Jira errors can contain local paths or customer data.
        emit(
            "command_failed",
            command=args.command,
            reason="Unexpected response or local state error; inspect setup and journal access",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
