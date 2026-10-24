"""Minimal schema migration runner: memory_records, reminders,
parent_pin, child_profiles, stories, engagement_sessions,
transcripts, lullabies, reading_profiles, reading_grapheme_mastery,
reading_exercises.
Each CREATE statement is
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

# Decision 0051: one row per child -- the per-learner fields
# reading/schema.py's ReadingProfile needs besides its mastery map
# (which lives in reading_grapheme_mastery below, one row per
# child+grapheme, matching this project's existing flat-row
# convention rather than a JSON blob).
_READING_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS reading_profiles (
    child_profile_id TEXT PRIMARY KEY,
    interest TEXT NOT NULL DEFAULT '',
    sight_words TEXT NOT NULL DEFAULT '',
    sessions_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_READING_GRAPHEME_MASTERY_TABLE = """
CREATE TABLE IF NOT EXISTS reading_grapheme_mastery (
    child_profile_id TEXT NOT NULL,
    grapheme TEXT NOT NULL,
    level TEXT NOT NULL,
    p_mastery REAL NOT NULL,
    opportunities INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0,
    last_seen_session INTEGER,
    PRIMARY KEY (child_profile_id, grapheme)
)
"""

_READING_GRAPHEME_MASTERY_CHILD_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reading_grapheme_mastery_child_profile
ON reading_grapheme_mastery (child_profile_id)
"""

# Decision 0052: a specific, parent-assigned passage (e.g. school
# homework) for one child -- deliberately separate from the shared
# `stories` table (Story Companion's library, read TO the child) and
# from LLM-generated books, which this table has no relation to.
# consumed_at is set once _run_reading_partner() has used it, so it's
# served to the child exactly once, not every session.
_READING_EXERCISES_TABLE = """
CREATE TABLE IF NOT EXISTS reading_exercises (
    id TEXT PRIMARY KEY,
    child_profile_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consumed_at TEXT
)
"""

_READING_EXERCISES_CHILD_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reading_exercises_child_profile
ON reading_exercises (child_profile_id)
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
    conn.execute(_READING_PROFILES_TABLE)
    conn.execute(_READING_GRAPHEME_MASTERY_TABLE)
    conn.execute(_READING_GRAPHEME_MASTERY_CHILD_INDEX)
    conn.execute(_READING_EXERCISES_TABLE)
    conn.execute(_READING_EXERCISES_CHILD_INDEX)
    _ensure_column(
        conn, "child_profiles", "speech_speed", "speech_speed REAL NOT NULL DEFAULT 1.0"
    )
    _ensure_column(conn, "child_profiles", "interest", "interest TEXT NOT NULL DEFAULT ''")
    _ensure_column(
        conn, "child_profiles", "reading_pace_wpm", "reading_pace_wpm REAL NOT NULL DEFAULT 45.0"
    )
    _ensure_column(
        conn,
        "child_profiles",
        "reading_font_size",
        "reading_font_size INTEGER NOT NULL DEFAULT 28",
    )
    _ensure_column(
        conn,
        "child_profiles",
        "reading_font_color",
        "reading_font_color TEXT NOT NULL DEFAULT 'white'",
    )
    # Decision 0067: where a child is mid-passage, persisted so a
    # session interrupted partway through a longer passage can resume
    # instead of restarting.
    _ensure_column(conn, "reading_profiles", "current_passage_key", "current_passage_key TEXT")
    _ensure_column(
        conn,
        "reading_profiles",
        "current_sentence_index",
        "current_sentence_index INTEGER NOT NULL DEFAULT 0",
    )
    # Decision 0104: slugs of story_library.py stories already read,
    # so the same one isn't re-served every session.
    _ensure_column(
        conn,
        "reading_profiles",
        "completed_library_stories",
        "completed_library_stories TEXT NOT NULL DEFAULT ''",
    )
    # Decision 0104: a parent-chosen starting phase (1-7,
    # reading/story_library.py's PHASES) -- NULL means no preference,
    # keeping today's LLM-generation-first behavior unchanged.
    _ensure_column(conn, "child_profiles", "preferred_phase", "preferred_phase INTEGER")
    conn.commit()
