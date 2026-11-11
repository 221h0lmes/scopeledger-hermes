"""ScopeLedger data lives under Hermes' per-profile plugin-data directory."""
from pathlib import Path
import os
import sqlite3
from contextlib import closing


def data_root():
    # For offline testing only: test fixture controls this override; never a remote input.
    override = os.environ.get("SCOPELEDGER_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    from plugins.plugin_storage import plugin_data_dir
    return plugin_data_dir("scopeledger")


def connect():
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "audit_receipts.sqlite3", timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_receipts (
        digest TEXT PRIMARY KEY, project_id TEXT NOT NULL, assessed_at TEXT NOT NULL,
        ready_minor INTEGER NOT NULL, possible_minor INTEGER NOT NULL,
        finding_count INTEGER NOT NULL, error_count INTEGER NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_receipts_v2 (
        digest TEXT NOT NULL, engine_version TEXT NOT NULL,
        project_id TEXT NOT NULL, assessed_at TEXT NOT NULL,
        ready_minor INTEGER NOT NULL, possible_minor INTEGER NOT NULL,
        finding_count INTEGER NOT NULL, error_count INTEGER NOT NULL,
        PRIMARY KEY (digest, engine_version)
    )""")
    return conn


def receipt(summary):
    from datetime import datetime, timezone
    with closing(connect()) as conn, conn:
        conn.execute("""INSERT OR IGNORE INTO audit_receipts
            (digest, project_id, assessed_at, ready_minor, possible_minor, finding_count, error_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (
            summary["digest"], summary["project_id"], datetime.now(timezone.utc).isoformat(),
            summary["totals"]["ready_minor"], summary["totals"]["possible_minor"],
            len(summary["findings"]), len(summary["errors"]),
        ))
        conn.execute("""INSERT OR IGNORE INTO audit_receipts_v2
            (digest, engine_version, project_id, assessed_at, ready_minor,
             possible_minor, finding_count, error_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
            summary["digest"], summary.get("engine_version", "unknown"),
            summary["project_id"], datetime.now(timezone.utc).isoformat(),
            summary["totals"]["ready_minor"], summary["totals"]["possible_minor"],
            len(summary["findings"]), len(summary["errors"]),
        ))
