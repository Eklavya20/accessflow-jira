import hashlib
import sqlite3
from datetime import UTC, datetime

from accessflow.config import SafetyError
from accessflow.jira import JiraClient


def default_probe_body(operation: str) -> str:
    return f"AccessFlow connectivity check. Sandbox test only. [accessflow-probe:{operation}]"


class ProbeJournal:
    """Small durable write-ahead journal for the one authorized connectivity comment.

    A committed reservation outlives a crash. A second invocation may reconcile it,
    but may never resend it just because a comment is not yet visible remotely.
    """

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS connectivity_probes (
            operation TEXT PRIMARY KEY, public INTEGER NOT NULL,
            state TEXT NOT NULL, comment_id TEXT, updated_at TEXT NOT NULL,
            body_sha256 TEXT
        )""")
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(connectivity_probes)")}
        if "body_sha256" not in columns:
            self.db.execute("ALTER TABLE connectivity_probes ADD COLUMN body_sha256 TEXT")
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def reserve(self, operation: str, public: bool, body: str | None = None) -> tuple[dict, bool]:
        body_hash = hashlib.sha256(
            (body if body is not None else default_probe_body(operation)).encode()
        ).hexdigest()
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO connectivity_probes "
                "(operation, public, state, comment_id, updated_at, body_sha256) "
                "VALUES (?, ?, 'pending', NULL, ?, ?)",
                (operation, int(public), datetime.now(UTC).isoformat(), body_hash),
            )
            new = cursor.rowcount == 1
            row = dict(
                self.db.execute(
                    "SELECT * FROM connectivity_probes WHERE operation = ?", (operation,)
                ).fetchone()
            )
        if bool(row["public"]) != public:
            raise SafetyError(
                "A probe already exists with different visibility; reconcile it first"
            )
        if row["body_sha256"] is None:
            legacy_hash = hashlib.sha256(default_probe_body(operation).encode()).hexdigest()
            if body_hash != legacy_hash:
                raise SafetyError("A legacy probe exists with different text; reconcile it first")
            with self.db:
                self.db.execute(
                    "UPDATE connectivity_probes SET body_sha256=? "
                    "WHERE operation=? AND body_sha256 IS NULL",
                    (legacy_hash, operation),
                )
            row["body_sha256"] = legacy_hash
        if row["body_sha256"] != body_hash:
            raise SafetyError("A probe already exists with different text; no new comment posted")
        return row, new

    def record(self, operation: str, state: str, comment_id: str) -> None:
        with self.db:
            self.db.execute(
                "UPDATE connectivity_probes SET state=?, comment_id=?, updated_at=? "
                "WHERE operation=?",
                (state, comment_id, datetime.now(UTC).isoformat(), operation),
            )


def verify_comment(
    client: JiraClient, issue_id: str, comment_id: str, body: str, public: bool, author_id: str
) -> dict:
    if not comment_id.isdigit():
        raise SafetyError("Jira returned an invalid comment ID; reconcile manually")
    comment = client.get(f"/rest/servicedeskapi/request/{issue_id}/comment/{comment_id}")
    if (
        str(comment.get("id")) != comment_id
        or comment.get("body") != body
        or comment.get("public") is not public
        or comment.get("author", {}).get("accountId") != author_id
    ):
        raise SafetyError("Comment body, author, or visibility failed read-back verification")
    return comment


def probe_comment(client: JiraClient, *, confirmed_key: str, public: bool) -> dict:
    settings = client.settings
    key = settings.require_target()
    if confirmed_key != key:
        raise SafetyError("Explicit confirmation must name the designated test issue exactly")
    author_id = client.identity()["accountId"]
    issue, _ = client.target()
    issue_id = str(issue["id"])
    permissions = client.permissions(issue_id)
    if not all(permissions[k] for k in ("BROWSE_PROJECTS", "ADD_COMMENTS")):
        raise SafetyError("Browse Projects and Add Comments must be confirmed before a probe")
    operation = hashlib.sha256(f"{settings.jira_site_url}|{issue_id}|probe-v1".encode()).hexdigest()
    body = settings.accessflow_probe_comment_body or default_probe_body(operation)
    result = {"issue_key": key, "issue_id": issue_id, "public": public, "body": body}
    if settings.accessflow_dry_run:
        return {**result, "write": "not_attempted", "mode": "dry_run"}
    with ProbeJournal(settings.database_path()) as journal:
        row, new = journal.reserve(operation, public, body)
        # Use JSM pagination, never the embedded/truncated issue comment collection.
        if row["comment_id"]:
            comment_id = row["comment_id"]
            verify_comment(client, issue_id, comment_id, body, public, author_id)
            outcome = "already_verified" if row["state"] == "verified" else "reconciled"
        else:
            comments = client.pages(f"/rest/servicedeskapi/request/{issue_id}/comment")
            matches = [
                c
                for c in comments
                if c.get("body") == body and c.get("author", {}).get("accountId") == author_id
            ]
            if len(matches) > 1:
                raise SafetyError("Multiple matching probe comments found; inspect Jira manually")
            if matches:
                comment_id = str(matches[0]["id"])
                verify_comment(client, issue_id, comment_id, body, public, author_id)
                outcome = "reconciled"
            elif not new:
                raise SafetyError(
                    "Probe outcome is uncertain or another run is active. No POST was retried. "
                    "Keep the journal; inspect Jira and rerun reconciliation later."
                )
            else:
                # Recheck project/desk immediately before the only remote mutation.
                current, _ = client.target()
                if str(current["id"]) != issue_id:
                    raise SafetyError("Target issue changed during preflight")
                created = client.post_probe_comment(issue_id, body, public)
                comment_id = str(created.get("id", ""))
                if not comment_id.isdigit():
                    raise SafetyError("Write response lacks a comment ID; reconcile before retry")
                journal.record(operation, "pending", comment_id)
                verify_comment(client, issue_id, comment_id, body, public, author_id)
                outcome = "created_and_verified"
        journal.record(operation, "verified", comment_id)
    return {**result, "comment_id": comment_id, "write": outcome}
