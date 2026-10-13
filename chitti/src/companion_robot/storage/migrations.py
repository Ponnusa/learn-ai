"""Minimal schema migration runner. Two migrations today (memory_records,
reminders); more arrive as storage/ gains parent-control state, etc.
Each statement is idempotent (CREATE TABLE/INDEX IF NOT EXISTS) so
re-running against an already-migrated database is always safe.
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

_REMINDERS_TABLE = """
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    child_profile_id TEXT NOT NULL,
    text TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    scheduled_tz_key TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    recurrence TEXT,
    is_alarm INTEGER NOT NULL
)
"""

_REMINDERS_CHILD_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reminders_child_profile
ON reminders (child_profile_id)
"""

_REMINDERS_DUE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reminders_due
ON reminders (enabled, scheduled_at)
"""


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(_MEMORY_RECORDS_TABLE)
    conn.execute(_MEMORY_RECORDS_CHILD_INDEX)
    conn.execute(_REMINDERS_TABLE)
    conn.execute(_REMINDERS_CHILD_INDEX)
    conn.execute(_REMINDERS_DUE_INDEX)
    conn.commit()
