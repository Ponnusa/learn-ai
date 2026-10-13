"""SQLite-backed repository for ReminderRecord (spec section 8).

A trusted local scheduler reads due_reminders()/mark_fired() -- the LLM
is never relied on to remember a future event or its timing (spec
section 8's explicit requirement).

Recurring reminders advance scheduled_at to the next occurrence by
re-interpreting the same wall-clock components in the reminder's own
timezone, rather than adding a raw 24h/7d timedelta to the aware
datetime -- that's the difference between "fires at 8am every day" and
"fires exactly 24 real hours later," which matters across a DST
transition (spec section 8: "handle ... daylight-saving changes").

This only works if the reminder's real IANA zone identity survives a
round trip through storage. A first version of this stored
scheduled_at.isoformat() directly, which bakes in the UTC offset *at
that instant* (e.g. "+02:00") and loses which zone it came from --
datetime.fromisoformat() parses that back as a fixed-offset timezone,
not zoneinfo.ZoneInfo("Europe/Helsinki"), so every recurrence advance
after the first reload silently used the wrong, stale offset. A unit
test crossing a real Europe/Helsinki DST transition caught this. Fixed
by storing the naive wall-clock time and the zone key separately, and
reconstructing a real ZoneInfo (or fixed offset, for non-IANA tzinfo)
on every load.

Not built here: natural-language date/time parsing or ambiguity
confirmation ("remind me tomorrow at 3") -- that's a conversation-level
concern once reminders are wired into a real conversation loop, not
this repository's job.

Device-restart persistence (spec section 8) depends on the caller using
a real SQLite file path, not ":memory:" -- that's a deployment/app.py
wiring concern, not something this module enforces.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from companion_robot.storage.migrations import run_migrations

from .schema import Recurrence, ReminderRecord, ReminderSource

_RECURRENCE_STEP = {
    Recurrence.DAILY: timedelta(days=1),
    Recurrence.WEEKLY: timedelta(days=7),
}


def _tz_to_key(tz) -> str:
    """Prefers the IANA zone key (ZoneInfo.key) when available, since
    that's what lets recurrence correctly track DST. Falls back to a
    fixed UTC-offset string for any other tzinfo -- a genuinely fixed
    offset has no DST to begin with, so plain timedelta math on it is
    already correct."""
    key = getattr(tz, "key", None)
    if key is not None:
        return key
    offset = tz.utcoffset(None)
    sign = "+" if offset >= timedelta(0) else "-"
    minutes = int(abs(offset).total_seconds() // 60)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def _key_to_tz(key: str):
    if key[0] in "+-":
        sign = 1 if key[0] == "+" else -1
        hours, minutes = key[1:].split(":")
        return timezone(sign * timedelta(hours=int(hours), minutes=int(minutes)))
    return ZoneInfo(key)


class ReminderRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def create(self, record: ReminderRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO reminders (
                id, child_profile_id, text, scheduled_at, scheduled_tz_key,
                source, created_at, updated_at, enabled, recurrence, is_alarm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.child_profile_id,
                record.text,
                record.scheduled_at.replace(tzinfo=None).isoformat(),
                _tz_to_key(record.scheduled_at.tzinfo),
                record.source.value,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
                int(record.enabled),
                record.recurrence.value if record.recurrence else None,
                int(record.is_alarm),
            ),
        )
        self._conn.commit()

    def get(self, record_id: str, child_profile_id: str) -> ReminderRecord | None:
        row = self._conn.execute(
            "SELECT * FROM reminders WHERE id = ? AND child_profile_id = ?",
            (record_id, child_profile_id),
        ).fetchone()
        return _row_to_record(row) if row else None

    def list_for_child(
        self, child_profile_id: str, enabled_only: bool = False
    ) -> list[ReminderRecord]:
        query = "SELECT * FROM reminders WHERE child_profile_id = ?"
        params: list = [child_profile_id]
        if enabled_only:
            query += " AND enabled = 1"
        rows = self._conn.execute(query, params).fetchall()
        return [_row_to_record(row) for row in rows]

    def update_text(self, record_id: str, child_profile_id: str, text: str) -> bool:
        cursor = self._conn.execute(
            "UPDATE reminders SET text = ?, updated_at = ? "
            "WHERE id = ? AND child_profile_id = ?",
            (text, _now_iso(), record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def set_enabled(self, record_id: str, child_profile_id: str, enabled: bool) -> bool:
        cursor = self._conn.execute(
            "UPDATE reminders SET enabled = ?, updated_at = ? "
            "WHERE id = ? AND child_profile_id = ?",
            (int(enabled), _now_iso(), record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def delete(self, record_id: str, child_profile_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM reminders WHERE id = ? AND child_profile_id = ?",
            (record_id, child_profile_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def due_reminders(self, now: datetime) -> list[ReminderRecord]:
        """Enabled reminders across all children whose scheduled time
        has passed -- the scheduler polls this directly, not any one
        child's list, since it doesn't know in advance which child's
        reminder is next due.

        Filters in Python, not SQL: scheduled_at is stored as a naive
        wall-clock string with its zone key in a separate column (see
        this module's docstring), so a different reminder's stored
        string isn't directly comparable to another's without first
        reconstructing a real aware datetime for each. The reminder
        count per device is small enough that this is the correct
        choice over a fragile SQL-level string comparison.
        """
        rows = self._conn.execute("SELECT * FROM reminders WHERE enabled = 1").fetchall()
        records = (_row_to_record(row) for row in rows)
        return [r for r in records if r.scheduled_at <= now]

    def mark_fired(
        self, record_id: str, child_profile_id: str, fired_at: datetime
    ) -> ReminderRecord | None:
        """Call once a due reminder has actually been delivered
        (spoken/alarm sounded) -- never before. One-time reminders are
        disabled (spec's "expiration"); recurring ones advance to their
        next occurrence and stay enabled."""
        record = self.get(record_id, child_profile_id)
        if record is None:
            return None

        if record.recurrence is None:
            self.set_enabled(record_id, child_profile_id, False)
            record.enabled = False
            return record

        next_time = _advance(record.scheduled_at, record.recurrence)
        self._conn.execute(
            "UPDATE reminders SET scheduled_at = ?, scheduled_tz_key = ?, "
            "updated_at = ? WHERE id = ? AND child_profile_id = ?",
            (
                next_time.replace(tzinfo=None).isoformat(),
                _tz_to_key(next_time.tzinfo),
                fired_at.isoformat(),
                record_id,
                child_profile_id,
            ),
        )
        self._conn.commit()
        record.scheduled_at = next_time
        return record


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _advance(dt: datetime, recurrence: Recurrence) -> datetime:
    step = _RECURRENCE_STEP[recurrence]
    naive_next = dt.replace(tzinfo=None) + step
    return naive_next.replace(tzinfo=dt.tzinfo)


def _row_to_record(row: sqlite3.Row) -> ReminderRecord:
    naive_scheduled = datetime.fromisoformat(row["scheduled_at"])
    scheduled_at = naive_scheduled.replace(tzinfo=_key_to_tz(row["scheduled_tz_key"]))
    return ReminderRecord(
        id=row["id"],
        child_profile_id=row["child_profile_id"],
        text=row["text"],
        scheduled_at=scheduled_at,
        source=ReminderSource(row["source"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        enabled=bool(row["enabled"]),
        recurrence=Recurrence(row["recurrence"]) if row["recurrence"] else None,
        is_alarm=bool(row["is_alarm"]),
    )
