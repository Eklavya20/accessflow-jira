"""Additive worker schema; the original journals remain intact."""

import json

from accessflow.config import SafetyError
from accessflow.persistence import Store, now


class WorkerStore(Store):
    def __init__(self, path):
        super().__init__(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS worker_schema (version INTEGER PRIMARY KEY);
            INSERT INTO worker_schema SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM worker_schema);
            CREATE TABLE IF NOT EXISTS worker_jobs (
                site TEXT NOT NULL, issue_id TEXT NOT NULL, issue_key TEXT NOT NULL,
                updated TEXT NOT NULL DEFAULT '', source_hash TEXT NOT NULL DEFAULT '',
                checked_at REAL NOT NULL DEFAULT 0, processed_at TEXT,
                state TEXT NOT NULL DEFAULT 'new', attempts INTEGER NOT NULL DEFAULT 0,
                retry_at REAL NOT NULL DEFAULT 0, error TEXT, outcome TEXT,
                operation_key TEXT, comment_id TEXT,
                PRIMARY KEY(site,issue_id));
            CREATE TABLE IF NOT EXISTS worker_runtime (
                site TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS worker_write_budget (
                policy_hash TEXT NOT NULL, operation_key TEXT NOT NULL,
                issue_id TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(policy_hash,operation_key), UNIQUE(policy_hash,issue_id));
        """)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            versions = [r[0] for r in self.db.execute("SELECT version FROM worker_schema")]
            if versions == [1]:
                self.db.execute("ALTER TABLE worker_jobs ADD COLUMN jira_updated_at TEXT")
                self.db.execute("UPDATE worker_schema SET version=2")
                versions = [2]
        if versions != [2]:
            self.db.close()
            raise SafetyError("Unsupported worker schema; preserve the database")
        self.db.commit()

    def job(self, site, issue_id):
        row = self.db.execute(
            "SELECT * FROM worker_jobs WHERE site=? AND issue_id=?", (site, issue_id)
        ).fetchone()
        return dict(row) if row else None

    def discover(self, site, issue_id, key):
        with self.db:
            self.db.execute(
                "INSERT INTO worker_jobs(site,issue_id,issue_key) VALUES (?,?,?) "
                "ON CONFLICT(site,issue_id) DO UPDATE SET issue_key=excluded.issue_key",
                (site, issue_id, key),
            )

    def update_job(self, site, issue_id, **values):
        allowed = {
            "updated",
            "source_hash",
            "checked_at",
            "processed_at",
            "state",
            "attempts",
            "retry_at",
            "error",
            "outcome",
            "operation_key",
            "comment_id",
            "jira_updated_at",
        }
        if not values or not set(values) <= allowed:
            raise SafetyError("Invalid worker state update")
        with self.db:
            self.db.execute(
                "UPDATE worker_jobs SET "
                + ",".join(k + "=?" for k in values)
                + " WHERE site=? AND issue_id=?",
                (*values.values(), site, issue_id),
            )

    def runtime(self, site):
        row = self.db.execute(
            "SELECT document FROM worker_runtime WHERE site=?", (site,)
        ).fetchone()
        return json.loads(row[0]) if row else {}

    def save_runtime(self, site, document):
        with self.db:
            self.db.execute(
                "INSERT INTO worker_runtime VALUES (?,?) ON CONFLICT(site) "
                "DO UPDATE SET document=excluded.document",
                (site, json.dumps(document)),
            )

    def reserve_write(self, policy_hash, operation_key, issue_id, maximum):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute(
                "SELECT operation_key FROM worker_write_budget WHERE policy_hash=? AND issue_id=?",
                (policy_hash, issue_id),
            ).fetchone()
            if existing:
                if existing[0] != operation_key:
                    raise SafetyError("Write policy permits only one revision per request")
                return
            count = self.db.execute(
                "SELECT count(*) FROM worker_write_budget WHERE policy_hash=?", (policy_hash,)
            ).fetchone()[0]
            if count >= maximum:
                raise SafetyError("Unattended write action budget exhausted")
            self.db.execute(
                "INSERT INTO worker_write_budget VALUES (?,?,?,?)",
                (policy_hash, operation_key, issue_id, now()),
            )

    def overview(self, site):
        rows = self.db.execute(
            "SELECT * FROM worker_jobs WHERE site=? ORDER BY issue_key", (site,)
        ).fetchall()
        jobs = [dict(r) for r in rows]
        counts = {}
        for job in jobs:
            if job["outcome"]:
                counts[job["outcome"]] = counts.get(job["outcome"], 0) + 1
        operations = self.db.execute(
            "SELECT state,count(*) FROM triage_operations WHERE site=? GROUP BY state", (site,)
        ).fetchall()
        return {
            "runtime": self.runtime(site),
            "jobs": jobs,
            "processed_requests": sum(j["processed_at"] is not None for j in jobs),
            "classification_counts": counts,
            "operation_counts": dict(operations),
        }
