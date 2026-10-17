"""Minimal schema migration runner: memory_records, reminders,
parent_pin, child_profiles, stories, engagement_sessions,
transcripts, lullabies. Each CREATE statement is
idempotent (CREATE TABLE/INDEX IF NOT EXISTS) so re-running against an
already-migrated database is always safe -- but that alone only
covers whole new tables. Adding a column to a table that already
exists (e.g. child_profiles, already live on the Pi before
speech_speed existed) is a no-op under CREATE TABLE IF NOT EXISTS,
since the table already exists -- it needs an explicit, checked
ALTER TABLE instead. See _ensure_column().
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
    story_companion_enabled INTEGER NOT NULL,
    speech_speed REAL NOT NULL DEFAULT 1.0
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

_ENGAGEMENT_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS engagement_sessions (
    id TEXT PRIMARY KEY,
    child_profile_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    turn_count INTEGER NOT NULL,
    word_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
"""

_ENGAGEMENT_SESSIONS_CHILD_INDEX = """
CREATE INDEX IF NOT EXISTS idx_engagement_sessions_child_profile
ON engagement_sessions (child_profile_id)
"""

_TRANSCRIPTS_TABLE = """
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    child_profile_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consent_or_authorization_status TEXT NOT NULL,
    retention_policy TEXT NOT NULL,
    expires_at TEXT
)
"""

_TRANSCRIPTS_CHILD_INDEX = """
CREATE INDEX IF NOT EXISTS idx_transcripts_child_profile
ON transcripts (child_profile_id)
"""

_LULLABIES_TABLE = """
CREATE TABLE IF NOT EXISTS lullabies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, add_column_ddl: str) -> None:
    """Idempotently adds a column to a table that may already exist
    without it. CREATE TABLE IF NOT EXISTS alone only defines new
    columns for a brand-new database -- it's a no-op for a table that
    already exists, so a schema change like adding speech_speed to
    child_profiles needs this instead."""
    existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {add_column_ddl}")


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(_MEMORY_RECORDS_TABLE)
    conn.execute(_MEMORY_RECORDS_CHILD_INDEX)
    conn.execute(_REMINDERS_TABLE)
    conn.execute(_REMINDERS_CHILD_INDEX)
    conn.execute(_REMINDERS_DUE_INDEX)
    conn.execute(_PARENT_PIN_TABLE)
    conn.execute(_CHILD_PROFILES_TABLE)
    conn.execute(_STORIES_TABLE)
    conn.execute(_ENGAGEMENT_SESSIONS_TABLE)
    conn.execute(_ENGAGEMENT_SESSIONS_CHILD_INDEX)
    conn.execute(_TRANSCRIPTS_TABLE)
    conn.execute(_TRANSCRIPTS_CHILD_INDEX)
    conn.execute(_LULLABIES_TABLE)
    _ensure_column(
        conn, "child_profiles", "speech_speed", "speech_speed REAL NOT NULL DEFAULT 1.0"
    )
    conn.commit()
