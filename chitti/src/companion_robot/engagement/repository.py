"""SQLite-backed repository for EngagementSession (decision 0023)."""
import sqlite3
from datetime import datetime

from companion_robot.storage.migrations import run_migrations

from .schema import EngagementMode, EngagementSession


class EngagementRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, session: EngagementSession) -> None:
        self._conn.execute(
            """
            INSERT INTO engagement_sessions (
                id, child_profile_id, mode, turn_count, word_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.child_profile_id,
                session.mode.value,
                session.turn_count,
                session.word_count,
                session.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def list_for_child(self, child_profile_id: str) -> list[EngagementSession]:
        rows = self._conn.execute(
            "SELECT * FROM engagement_sessions WHERE child_profile_id = ? ORDER BY created_at",
            (child_profile_id,),
        ).fetchall()
        return [_row_to_session(row) for row in rows]

    def latest_for_child(self, child_profile_id: str) -> EngagementSession | None:
        sessions = self.list_for_child(child_profile_id)
        return max(sessions, key=lambda s: s.created_at, default=None)


def _row_to_session(row: sqlite3.Row) -> EngagementSession:
    return EngagementSession(
        id=row["id"],
        child_profile_id=row["child_profile_id"],
        mode=EngagementMode(row["mode"]),
        turn_count=row["turn_count"],
        word_count=row["word_count"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
