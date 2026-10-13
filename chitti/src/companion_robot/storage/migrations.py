"""Minimal schema migration runner. One migration today (memory_records);
more arrive as storage/ gains reminders, parent-control state, etc. Each
statement is idempotent (CREATE TABLE/INDEX IF NOT EXISTS) so re-running
against an already-migrated database is always safe.
"""
import sqlite3

_MEMORY_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_records (
    id TEXT PRIMARY KEY,
    child_profile_id TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    source TEXT NOT NULL,
    consent_or_authorization_status TEXT NOT NULL,
    retention_policy TEXT NOT NULL,
    schema_version INTEGER NOT NULL
)
"""

_MEMORY_RECORDS_CHILD_INDEX = """
CREATE INDEX IF NOT EXISTS idx_memory_records_child_profile
ON memory_records (child_profile_id)
"""


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(_MEMORY_RECORDS_TABLE)
    conn.execute(_MEMORY_RECORDS_CHILD_INDEX)
    conn.commit()
