"""Parent-assigned reading exercises (decision 0052): a specific
passage for one child -- e.g. school homework -- kept separate from
both the shared `stories` library (Story Companion reads TO the
child) and Reading Partner's LLM-generated decodable books. Content
is trusted as-is (no safety screening), same reasoning risk register
#14 already applies to parent-uploaded stories and lullaby audio: the
parent is the authorizing adult for their own child.

Consumed exactly once: _run_reading_partner() marks an exercise
consumed as soon as it's picked up, so the child reads the assigned
passage once, not every session, and the mode falls back to its
LLM-generated books afterward.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from companion_robot.storage.migrations import run_migrations


@dataclass
class ReadingExerciseRecord:
    id: str
    child_profile_id: str
    title: str
    content: str
    created_at: datetime
    consumed_at: datetime | None = None


class ReadingExerciseRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, exercise: ReadingExerciseRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO reading_exercises (
                id, child_profile_id, title, content, created_at, consumed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                exercise.id,
                exercise.child_profile_id,
                exercise.title,
                exercise.content,
                exercise.created_at.isoformat(),
                exercise.consumed_at.isoformat() if exercise.consumed_at else None,
            ),
        )
        self._conn.commit()

    def list_for_child(self, child_profile_id: str) -> list[ReadingExerciseRecord]:
        rows = self._conn.execute(
            "SELECT * FROM reading_exercises WHERE child_profile_id = ? ORDER BY created_at",
            (child_profile_id,),
        ).fetchall()
        return [_row_to_exercise(row) for row in rows]

    def next_pending_for_child(self, child_profile_id: str) -> ReadingExerciseRecord | None:
        row = self._conn.execute(
            "SELECT * FROM reading_exercises WHERE child_profile_id = ? "
            "AND consumed_at IS NULL ORDER BY created_at LIMIT 1",
            (child_profile_id,),
        ).fetchone()
        return _row_to_exercise(row) if row else None

    def mark_consumed(self, exercise_id: str) -> None:
        self._conn.execute(
            "UPDATE reading_exercises SET consumed_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), exercise_id),
        )
        self._conn.commit()

    def delete(self, exercise_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM reading_exercises WHERE id = ?", (exercise_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0


def _row_to_exercise(row: sqlite3.Row) -> ReadingExerciseRecord:
    return ReadingExerciseRecord(
        id=row["id"],
        child_profile_id=row["child_profile_id"],
        title=row["title"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        consumed_at=datetime.fromisoformat(row["consumed_at"]) if row["consumed_at"] else None,
    )
