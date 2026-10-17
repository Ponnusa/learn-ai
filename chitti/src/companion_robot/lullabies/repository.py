import sqlite3
from datetime import datetime

from companion_robot.storage.migrations import run_migrations

from .schema import LullabyRecord


class LullabyRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, lullaby: LullabyRecord) -> None:
        self._conn.execute(
            "INSERT INTO lullabies (id, title, created_at) VALUES (?, ?, ?)",
            (lullaby.id, lullaby.title, lullaby.created_at.isoformat()),
        )
        self._conn.commit()

    def get(self, lullaby_id: str) -> LullabyRecord | None:
        row = self._conn.execute(
            "SELECT * FROM lullabies WHERE id = ?", (lullaby_id,)
        ).fetchone()
        return _row_to_lullaby(row) if row else None

    def list_all(self) -> list[LullabyRecord]:
        rows = self._conn.execute("SELECT * FROM lullabies ORDER BY title").fetchall()
        return [_row_to_lullaby(row) for row in rows]

    def delete(self, lullaby_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM lullabies WHERE id = ?", (lullaby_id,))
        self._conn.commit()
        return cursor.rowcount > 0


def _row_to_lullaby(row: sqlite3.Row) -> LullabyRecord:
    return LullabyRecord(
        id=row["id"],
        title=row["title"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
