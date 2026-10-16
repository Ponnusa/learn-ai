"""SQLite-backed repository for TranscriptRecord (decision 0038).

Same shape as memory/repository.py's MemoryRepository: every read/
delete is scoped to one child_profile_id, and an expired record is
excluded from list_for_child() even before purge_expired() runs, so
"expired" behaves like "already deleted" for every normal read --
same reasoning as memory/repository.py's own module docstring.
"""
import sqlite3
from datetime import datetime, timezone

from companion_robot.engagement.schema import EngagementMode
from companion_robot.memory.schema import ConsentStatus
from companion_robot.storage.migrations import run_migrations

from .schema import TranscriptRecord


class TranscriptRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, record: TranscriptRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO transcripts (
                id, child_profile_id, mode, content, created_at,
                consent_or_authorization_status, retention_policy, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.child_profile_id,
                record.mode.value,
                record.content,
                record.created_at.isoformat(),
                record.consent_or_authorization_status.value,
                record.retention_policy,
                record.expires_at.isoformat() if record.expires_at else None,
            ),
        )
        self._conn.commit()

    def list_for_child(self, child_profile_id: str) -> list[TranscriptRecord]:
        rows = self._conn.execute(
            "SELECT * FROM transcripts WHERE child_profile_id = ? ORDER BY created_at",
            (child_profile_id,),
        ).fetchall()
        records = (_row_to_record(row) for row in rows)
        return [r for r in records if not _is_expired(r)]

    def delete(self, record_id: str, child_profile_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM transcripts WHERE id = ? AND child_profile_id = ?",
            (record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def purge_expired(self) -> int:
        cursor = self._conn.execute(
            "DELETE FROM transcripts WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (datetime.now(timezone.utc).isoformat(),),
        )
        self._conn.commit()
        return cursor.rowcount


def _row_to_record(row: sqlite3.Row) -> TranscriptRecord:
    return TranscriptRecord(
        id=row["id"],
        child_profile_id=row["child_profile_id"],
        mode=EngagementMode(row["mode"]),
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        consent_or_authorization_status=ConsentStatus(row["consent_or_authorization_status"]),
        retention_policy=row["retention_policy"],
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
    )


def _is_expired(record: TranscriptRecord) -> bool:
    if record.expires_at is None:
        return False
    return record.expires_at <= datetime.now(timezone.utc)
