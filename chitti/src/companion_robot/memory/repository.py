"""SQLite-backed repository for MemoryRecord (spec section 6).

Enforces invariants beyond what the dataclass alone can:
- conversation_context is refused outright -- it's session-only by
  definition (schema.py's MemoryCategory docstring), never a durable
  row here.
- Every read/update/delete is scoped to one child_profile_id, so a
  record can never be returned or edited across sibling profiles
  (decision 0003) -- enforced in the SQL itself (id AND
  child_profile_id), not left to callers to double-check.
- Expired records are excluded from get()/list_for_child() even before
  purge_expired() runs, so "expired" behaves like "already deleted" for
  every normal read (spec section 13's acceptance criterion).

All datetime fields on MemoryRecord must be timezone-aware (UTC) --
comparing a naive and an aware datetime raises, by design, rather than
silently assuming a timezone.
"""
import sqlite3
from datetime import datetime, timezone

from companion_robot.storage.migrations import run_migrations

from .schema import ConsentStatus, MemoryCategory, MemoryRecord, MemorySource


class MemoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, record: MemoryRecord) -> None:
        if record.category == MemoryCategory.CONVERSATION_CONTEXT:
            raise ValueError(
                "conversation_context must never be persisted as a durable "
                "MemoryRecord -- it's session-only by definition"
            )
        self._conn.execute(
            """
            INSERT INTO memory_records (
                id, child_profile_id, category, content, created_at,
                updated_at, expires_at, source,
                consent_or_authorization_status, retention_policy,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.child_profile_id,
                record.category.value,
                record.content,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
                record.expires_at.isoformat() if record.expires_at else None,
                record.source.value,
                record.consent_or_authorization_status.value,
                record.retention_policy,
                record.schema_version,
            ),
        )
        self._conn.commit()

    def get(self, record_id: str, child_profile_id: str) -> MemoryRecord | None:
        row = self._conn.execute(
            "SELECT * FROM memory_records WHERE id = ? AND child_profile_id = ?",
            (record_id, child_profile_id),
        ).fetchone()
        if row is None:
            return None
        record = _row_to_record(row)
        return None if _is_expired(record) else record

    def list_for_child(
        self, child_profile_id: str, category: MemoryCategory | None = None
    ) -> list[MemoryRecord]:
        query = "SELECT * FROM memory_records WHERE child_profile_id = ?"
        params: list = [child_profile_id]
        if category is not None:
            query += " AND category = ?"
            params.append(category.value)
        rows = self._conn.execute(query, params).fetchall()
        records = (_row_to_record(row) for row in rows)
        return [r for r in records if not _is_expired(r)]

    def update_content(self, record_id: str, child_profile_id: str, content: str) -> bool:
        cursor = self._conn.execute(
            "UPDATE memory_records SET content = ?, updated_at = ? "
            "WHERE id = ? AND child_profile_id = ?",
            (content, _now_iso(), record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def update_consent(
        self, record_id: str, child_profile_id: str, status: ConsentStatus
    ) -> bool:
        cursor = self._conn.execute(
            "UPDATE memory_records SET consent_or_authorization_status = ?, "
            "updated_at = ? WHERE id = ? AND child_profile_id = ?",
            (status.value, _now_iso(), record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, record_id: str, child_profile_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM memory_records WHERE id = ? AND child_profile_id = ?",
            (record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def purge_expired(self) -> int:
        cursor = self._conn.execute(
            "DELETE FROM memory_records WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (_now_iso(),),
        )
        self._conn.commit()
        return cursor.rowcount


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        child_profile_id=row["child_profile_id"],
        category=MemoryCategory(row["category"]),
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        source=MemorySource(row["source"]),
        consent_or_authorization_status=ConsentStatus(row["consent_or_authorization_status"]),
        retention_policy=row["retention_policy"],
        schema_version=row["schema_version"],
    )


def _is_expired(record: MemoryRecord) -> bool:
    if record.expires_at is None:
        return False
    return record.expires_at <= datetime.now(timezone.utc)
