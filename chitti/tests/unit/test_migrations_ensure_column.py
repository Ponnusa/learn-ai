"""Unit tests for storage.migrations._ensure_column -- the real-world
scenario that matters: adding speech_speed to a child_profiles table
that already existed (and was already live on the Pi) before that
column was added.
"""
from companion_robot.storage.migrations import _ensure_column, run_migrations
from companion_robot.storage.sqlite import connect


def test_ensure_column_adds_missing_column_with_default():
    conn = connect(":memory:")
    # Simulate a pre-existing table from before speech_speed existed --
    # same shape run_migrations() would have created with an older
    # version of _CHILD_PROFILES_TABLE.
    conn.execute(
        """
        CREATE TABLE child_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            teachable_friend_enabled INTEGER NOT NULL,
            story_companion_enabled INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO child_profiles VALUES ('p1', 'Anna', 7, 'x', 'x', 1, 1)"
    )
    conn.commit()

    _ensure_column(
        conn, "child_profiles", "speech_speed", "speech_speed REAL NOT NULL DEFAULT 1.0"
    )

    row = conn.execute("SELECT speech_speed FROM child_profiles WHERE id = 'p1'").fetchone()
    assert row["speech_speed"] == 1.0


def test_ensure_column_adds_interest_column_with_default():
    """Same scenario, for decision 0051's follow-up: Reading Partner's
    interest field, added to child_profiles after it already existed
    and had rows."""
    conn = connect(":memory:")
    conn.execute(
        """
        CREATE TABLE child_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            teachable_friend_enabled INTEGER NOT NULL,
            story_companion_enabled INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO child_profiles VALUES ('p1', 'Anna', 7, 'x', 'x', 1, 1)"
    )
    conn.commit()

    _ensure_column(conn, "child_profiles", "interest", "interest TEXT NOT NULL DEFAULT ''")

    row = conn.execute("SELECT interest FROM child_profiles WHERE id = 'p1'").fetchone()
    assert row["interest"] == ""


def test_ensure_column_is_a_noop_if_column_already_present():
    conn = connect(":memory:")
    run_migrations(conn)  # already-current schema, speech_speed included

    # Must not raise "duplicate column name" on a second call.
    _ensure_column(
        conn, "child_profiles", "speech_speed", "speech_speed REAL NOT NULL DEFAULT 1.0"
    )
    _ensure_column(
        conn, "child_profiles", "speech_speed", "speech_speed REAL NOT NULL DEFAULT 1.0"
    )


def test_run_migrations_is_safe_against_a_table_missing_the_new_column():
    """End-to-end version of the scenario found live: a database
    created before speech_speed existed must still work after
    pulling code that expects the column."""
    conn = connect(":memory:")
    conn.execute(
        """
        CREATE TABLE child_profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            teachable_friend_enabled INTEGER NOT NULL,
            story_companion_enabled INTEGER NOT NULL
        )
        """
    )
    conn.commit()

    run_migrations(conn)  # must not raise, and must add the column

    columns = {row[1] for row in conn.execute("PRAGMA table_info(child_profiles)").fetchall()}
    assert "speech_speed" in columns
    assert "interest" in columns
    assert "preferred_phase" in columns  # decision 0104
    assert "last_greeted_date" in columns  # decision 0108


def test_run_migrations_adds_completed_library_stories_to_reading_profiles():
    """Decision 0104: the same pre-existing-table scenario, for
    reading_profiles -- a database created before the library feature
    existed must still work after pulling code that expects the
    column."""
    conn = connect(":memory:")
    conn.execute(
        """
        CREATE TABLE reading_profiles (
            child_profile_id TEXT PRIMARY KEY,
            interest TEXT NOT NULL DEFAULT '',
            sight_words TEXT NOT NULL DEFAULT '',
            sessions_completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    run_migrations(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(reading_profiles)").fetchall()}
    assert "completed_library_stories" in columns
