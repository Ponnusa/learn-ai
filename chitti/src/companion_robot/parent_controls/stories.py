"""Story library (decision 0003): preloaded or parent-uploaded text,
managed from the Parent Controls web UI. Shared across all child
profiles on the device, not scoped to one child -- matches
architecture.md's "preloaded story library" framing. Content is
trusted as-is (format/size only, no moderation) since the parent is
the authorizing adult for their own child (risk register #14).
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from companion_robot.storage.migrations import run_migrations


@dataclass
class StoryRecord:
    id: str
    title: str
    content: str
    created_at: datetime


class StoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, story: StoryRecord) -> None:
        self._conn.execute(
            "INSERT INTO stories (id, title, content, created_at) VALUES (?, ?, ?, ?)",
            (story.id, story.title, story.content, story.created_at.isoformat()),
        )
        self._conn.commit()

    def get(self, story_id: str) -> StoryRecord | None:
        row = self._conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        return _row_to_story(row) if row else None

    def list_all(self) -> list[StoryRecord]:
        rows = self._conn.execute("SELECT * FROM stories ORDER BY title").fetchall()
        return [_row_to_story(row) for row in rows]

    def delete(self, story_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        self._conn.commit()
        return cursor.rowcount > 0


def _row_to_story(row: sqlite3.Row) -> StoryRecord:
    return StoryRecord(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
