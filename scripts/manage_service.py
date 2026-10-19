"""Native Windows detached startup; administration uses local authenticated HTTP."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx

from accessflow.config import SafetyError, Settings

ROOT = Path(__file__).resolve().parents[1]


def request(settings, method, path):
    # Local API only. Do not send credentials to redirects or remote hosts.
    with httpx.Client(
        base_url=f"http://127.0.0.1:{settings.accessflow_port}",
        timeout=5,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        response = client.request(
            method,
            path,
            headers={
                "Authorization": "Bearer " + settings.accessflow_admin_token.get_secret_value()
            },
        )
        response.raise_for_status()
        return response.json()


def start(settings):
    try:
        request(settings, "GET", "/admin/status")
        raise SafetyError("An authenticated AccessFlow service is already running")
    except httpx.ConnectError:
        pass
    if os.name != "nt":
        raise SafetyError(
            "This launcher is for Windows; use Compose or the foreground serve command"
        )
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    with (reports / "native-service.stdout.log").open("ab") as stdout:
        with (reports / "native-service.stderr.log").open("ab") as stderr:
            child = subprocess.Popen(
                [sys.executable, "-m", "accessflow", "serve"],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                close_fds=True,
                creationflags=subprocess.CREATE_NO_WINDOW
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
    for _ in range(60):
        if child.poll() is not None:
            raise SafetyError(
                "Service exited during startup; inspect local reports/native-service.stderr.log"
            )
        try:
            request(settings, "GET", "/admin/status")
            return {
                "started": True,
                "pid": child.pid,
                "port": settings.accessflow_port,
                "health": "Starting: first real Jira poll must complete before health passes",
            }
        except httpx.ConnectError:
            time.sleep(0.25)
    raise SafetyError("Startup timeout; inspect the background process and local logs")


def stop(settings):
    request(settings, "POST", "/admin/shutdown")
    for _ in range(45):
        time.sleep(1)
        try:
            request(settings, "GET", "/admin/status")
        except httpx.ConnectError:
            return {"stopped": True}
    raise SafetyError("Graceful shutdown is still pending; inspect the local service logs")


def main():
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "status", "health", "backup"])
    args = parser.parse_args()
    settings = Settings()
    if args.command == "start":
        result = start(settings)
    elif args.command == "stop":
        result = stop(settings)
    elif args.command == "backup":
        source = settings.database_path()
        if not source.exists():
            raise SafetyError("No database exists to back up")
        target = ROOT / "data" / ("backup-" + time.strftime("%Y%m%d-%H%M%S") + ".db")
        target.parent.mkdir(exist_ok=True)
        with sqlite3.connect(source) as original, sqlite3.connect(target) as copy:
            original.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SafetyError("Backup integrity check failed")
        result = {"backup": str(target.relative_to(ROOT)), "integrity": "ok"}
    else:
        result = request(
            settings, "GET", "/health" if args.command == "health" else "/admin/status"
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, SafetyError, OSError, sqlite3.Error):
        print(
            "Service operation failed; inspect local configuration, health and redacted logs",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
