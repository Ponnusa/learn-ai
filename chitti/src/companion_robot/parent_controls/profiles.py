"""Child profile management (decision 0003): name, age, and feature
toggles, managed from the Parent Controls web UI. `id` matching this
module's profiles is what `memory/`, `reminders/`, and `conversation/`
mean by `child_profile_id` -- no foreign-key enforcement at the DB
level (kept loosely coupled, same spirit as the rest of this codebase).
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from companion_robot.storage.migrations import run_migrations


@dataclass
class ChildProfile:
    id: str
    name: str
    age: int
    created_at: datetime
    updated_at: datetime
    teachable_friend_enabled: bool = True
    story_companion_enabled: bool = True
    # Passed straight through to OpenAITTSBackend's speed parameter
    # (0.25-4.0, default 1.0). Parent-controlled rather than a child
    # voice command -- keeps control with the parent, consistent with
    # age/feature toggles already living here, rather than adding an
    # unvalidated "talk slower" voice command surface for the child.
    speech_speed: float = 1.0
    # Decision 0051 follow-up: themes Reading Partner's LLM-generated
    # books ("a story about dinosaurs"). Parent-settable here, same as
    # age/speech_speed, rather than a CLI flag -- Chitti has no
    # argparse-style entry point the way phono-storyforge's own
    # tutor_cli.py did. Reading-only for now, not fed into any other
    # mode's prompt.
    interest: str = ""
    # Decision 0053: Reading Partner's teleprompter display -- how
    # fast the word-highlight advances (words per minute), and the
    # on-screen font size/color. Parent-settable here, same as
    # speech_speed/interest. Color is one of a short vetted list
    # (device/screen_face.py's _READING_FONT_COLORS), not a free
    # picker, so a parent can't accidentally choose something
    # unreadable against the display's dark background.
    reading_pace_wpm: float = 45.0
    reading_font_size: int = 28
    reading_font_color: str = "white"


class ChildProfileRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, profile: ChildProfile) -> None:
        self._conn.execute(
            """
            INSERT INTO child_profiles (
                id, name, age, created_at, updated_at,
                teachable_friend_enabled, story_companion_enabled, speech_speed, interest,
                reading_pace_wpm, reading_font_size, reading_font_color
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.id,
                profile.name,
                profile.age,
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
                int(profile.teachable_friend_enabled),
                int(profile.story_companion_enabled),
                profile.speech_speed,
                profile.interest,
                profile.reading_pace_wpm,
                profile.reading_font_size,
                profile.reading_font_color,
            ),
        )
        self._conn.commit()

    def get(self, profile_id: str) -> ChildProfile | None:
        row = self._conn.execute(
            "SELECT * FROM child_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return _row_to_profile(row) if row else None

    def list_all(self) -> list[ChildProfile]:
        rows = self._conn.execute("SELECT * FROM child_profiles ORDER BY name").fetchall()
        return [_row_to_profile(row) for row in rows]

    def update(
        self,
        profile_id: str,
        name: str | None = None,
        age: int | None = None,
        teachable_friend_enabled: bool | None = None,
        story_companion_enabled: bool | None = None,
        speech_speed: float | None = None,
        interest: str | None = None,
        reading_pace_wpm: float | None = None,
        reading_font_size: int | None = None,
        reading_font_color: str | None = None,
    ) -> bool:
        existing = self.get(profile_id)
        if existing is None:
            return False
        name = existing.name if name is None else name
        age = existing.age if age is None else age
        teachable_friend_enabled = (
            existing.teachable_friend_enabled
            if teachable_friend_enabled is None
            else teachable_friend_enabled
        )
        story_companion_enabled = (
            existing.story_companion_enabled
            if story_companion_enabled is None
            else story_companion_enabled
        )
        speech_speed = existing.speech_speed if speech_speed is None else speech_speed
        interest = existing.interest if interest is None else interest
        reading_pace_wpm = (
            existing.reading_pace_wpm if reading_pace_wpm is None else reading_pace_wpm
        )
        reading_font_size = (
            existing.reading_font_size if reading_font_size is None else reading_font_size
        )
        reading_font_color = (
            existing.reading_font_color if reading_font_color is None else reading_font_color
        )
        self._conn.execute(
            "UPDATE child_profiles SET name = ?, age = ?, updated_at = ?, "
            "teachable_friend_enabled = ?, story_companion_enabled = ?, "
            "speech_speed = ?, interest = ?, reading_pace_wpm = ?, "
            "reading_font_size = ?, reading_font_color = ? WHERE id = ?",
            (
                name,
                age,
                datetime.now(timezone.utc).isoformat(),
                int(teachable_friend_enabled),
                int(story_companion_enabled),
                speech_speed,
                interest,
                reading_pace_wpm,
                reading_font_size,
                reading_font_color,
                profile_id,
            ),
        )
        self._conn.commit()
        return True

    def delete(self, profile_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM child_profiles WHERE id = ?", (profile_id,))
        self._conn.commit()
        return cursor.rowcount > 0


def _row_to_profile(row: sqlite3.Row) -> ChildProfile:
    return ChildProfile(
        id=row["id"],
        name=row["name"],
        age=row["age"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        teachable_friend_enabled=bool(row["teachable_friend_enabled"]),
        story_companion_enabled=bool(row["story_companion_enabled"]),
        speech_speed=row["speech_speed"],
        interest=row["interest"],
        reading_pace_wpm=row["reading_pace_wpm"],
        reading_font_size=row["reading_font_size"],
        reading_font_color=row["reading_font_color"],
    )
