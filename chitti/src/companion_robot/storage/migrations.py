"""Minimal schema migration runner: memory_records, reminders,
parent_pin, child_profiles, stories. Each statement is idempotent
(CREATE TABLE/INDEX IF NOT EXISTS) so re-running against an
already-migrated database is always safe.
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

_PARENT_PIN_TABLE = """
CREATE TABLE IF NOT EXISTS parent_pin (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    pin_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CHILD_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS child_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    teachable_friend_enabled INTEGER NOT NULL,
    story_companion_enabled INTEGER NOT NULL
)
"""

_STORIES_TABLE = """
CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(_MEMORY_RECORDS_TABLE)
    conn.execute(_MEMORY_RECORDS_CHILD_INDEX)
    conn.execute(_REMINDERS_TABLE)
    conn.execute(_REMINDERS_CHILD_INDEX)
    conn.execute(_REMINDERS_DUE_INDEX)
    conn.execute(_PARENT_PIN_TABLE)
    conn.execute(_CHILD_PROFILES_TABLE)
    conn.execute(_STORIES_TABLE)
    conn.commit()
