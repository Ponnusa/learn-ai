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


class ChildProfileRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, profile: ChildProfile) -> None:
        self._conn.execute(
            """
            INSERT INTO child_profiles (
                id, name, age, created_at, updated_at,
                teachable_friend_enabled, story_companion_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.id,
                profile.name,
                profile.age,
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
                int(profile.teachable_friend_enabled),
                int(profile.story_companion_enabled),
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
        self._conn.execute(
            "UPDATE child_profiles SET name = ?, age = ?, updated_at = ?, "
            "teachable_friend_enabled = ?, story_companion_enabled = ? WHERE id = ?",
            (
                name,
                age,
                datetime.now(timezone.utc).isoformat(),
                int(teachable_friend_enabled),
                int(story_companion_enabled),
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
    )
