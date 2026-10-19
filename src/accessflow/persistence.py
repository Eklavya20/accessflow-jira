import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from accessflow.config import SafetyError
from accessflow.domain import digest


def now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def issue_lock(database: Path, site: str, issue_id: str):
    """OS-owned lock, released on process exit; no unsafe expired-lease takeover.

    This is a single-host, local-filesystem implementation for Windows/Linux.
    Persistent action intents independently protect remote crash uncertainty.
    """
    directory = database.parent / (database.name + ".locks")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (digest([site, issue_id]) + ".lock")
    handle = path.open("a+b")
    acquired = False
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise SafetyError(
                "This issue is already being processed; retry when the run completes"
            ) from None
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS triage_schema (version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO triage_schema VALUES (1);
            CREATE TABLE IF NOT EXISTS triage_issues (
                site TEXT NOT NULL, issue_id TEXT NOT NULL, issue_key TEXT NOT NULL,
                semantic_hash TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY (site, issue_id));
            CREATE TABLE IF NOT EXISTS triage_results (
                id INTEGER PRIMARY KEY, site TEXT NOT NULL, issue_id TEXT NOT NULL,
                issue_key TEXT NOT NULL, operation_key TEXT NOT NULL,
                source_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS triage_operations (
                operation_key TEXT PRIMARY KEY, site TEXT NOT NULL, issue_id TEXT NOT NULL,
                issue_key TEXT NOT NULL, revision INTEGER NOT NULL,
                body TEXT NOT NULL, state TEXT NOT NULL, comment_id TEXT, author_id TEXT,
                error TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS triage_audit (
                id INTEGER PRIMARY KEY, site TEXT NOT NULL, issue_key TEXT NOT NULL,
                event TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS triage_results_issue
                ON triage_results(site, issue_key, id);
            CREATE INDEX IF NOT EXISTS triage_audit_issue
                ON triage_audit(site, issue_key, id);
        """)
        if [r[0] for r in self.db.execute("SELECT version FROM triage_schema")] != [1]:
            self.db.close()
            raise SafetyError("Unsupported triage database schema; do not change it manually")
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def audit(self, site: str, key: str, event: str, **details):
        with self.db:
            self.db.execute(
                "INSERT INTO triage_audit VALUES (NULL, ?, ?, ?, ?, ?)",
                (site, key, event, json.dumps(details), now()),
            )

    def revision(self, site: str, issue_id: str, key: str, semantic_hash: str) -> int:
        with self.db:
            row = self.db.execute(
                "SELECT * FROM triage_issues WHERE site=? AND issue_id=?", (site, issue_id)
            ).fetchone()
            revision = 1 if not row else row["revision"] + (row["semantic_hash"] != semantic_hash)
            self.db.execute(
                "INSERT INTO triage_issues VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(site,issue_id) DO UPDATE SET issue_key=excluded.issue_key, "
                "semantic_hash=excluded.semantic_hash, revision=excluded.revision",
                (site, issue_id, key, semantic_hash, revision),
            )
        return revision

    def operation(self, operation_key: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM triage_operations WHERE operation_key=?", (operation_key,)
        ).fetchone()
        return dict(row) if row else None

    def plan(
        self, site: str, key: str, issue_id: str, revision: int, operation_key: str, body: str
    ) -> dict:
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO triage_operations "
                "VALUES (?, ?, ?, ?, ?, ?, 'planned', NULL, NULL, NULL, ?)",
                (operation_key, site, issue_id, key, revision, body, now()),
            )
        operation = self.operation(operation_key)
        if operation["body"] != body:
            raise SafetyError(
                "Stored action and proposed comment differ; manual inspection required"
            )
        return operation

    def state(self, operation_key: str, state: str, *, comment_id=None, author_id=None, error=None):
        with self.db:
            self.db.execute(
                "UPDATE triage_operations SET state=?, "
                "comment_id=COALESCE(?,comment_id), author_id=COALESCE(?,author_id), "
                "error=?, updated_at=? WHERE operation_key=?",
                (state, comment_id, author_id, error, now(), operation_key),
            )

    def save_result(self, site: str, source_hash: str, result) -> None:
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO triage_results VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)",
                (
                    site,
                    result.issue_id,
                    result.issue_key,
                    result.operation_key,
                    source_hash,
                    result.model_dump_json(),
                    now(),
                ),
            )
            result.result_id = cursor.lastrowid
            self.db.execute(
                "UPDATE triage_results SET result_json=? WHERE id=?",
                (result.model_dump_json(), result.result_id),
            )

    def update_result(self, result):
        with self.db:
            self.db.execute(
                "UPDATE triage_results SET result_json=? WHERE id=?",
                (result.model_dump_json(), result.result_id),
            )

    def latest(self, site: str, key: str) -> dict:
        row = self.db.execute(
            "SELECT result_json, operation_key FROM triage_results "
            "WHERE site=? AND issue_key=? ORDER BY id DESC LIMIT 1",
            (site, key),
        ).fetchone()
        if not row:
            raise SafetyError("No durable result found for this issue")
        result = json.loads(row["result_json"])
        operation = self.operation(row["operation_key"])
        result.update(write_status=operation["state"], comment_id=operation["comment_id"])
        return result

    def history(self, site: str, key: str, limit: int = 100) -> list[dict]:
        rows = self.db.execute(
            "SELECT id,event,details_json,created_at FROM triage_audit "
            "WHERE site=? AND issue_key=? ORDER BY id DESC LIMIT ?",
            (site, key, limit),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "event": r["event"],
                "details": json.loads(r["details_json"]),
                "created_at": r["created_at"],
            }
            for r in reversed(rows)
        ]
