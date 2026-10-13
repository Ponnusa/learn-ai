"""Parent-control authentication (spec section 9: authentication for
parent controls; decision 0002's PIN-gated, LAN-only web UI).

PINs are hashed with werkzeug's generate_password_hash/check_password_hash
(a dependency Flask already brings in) -- never rolling custom crypto.
RateLimiter is server-side, in-memory state, not cookie/session-based,
so clearing cookies can't reset a lockout. One admin PIN per device, so
a single global counter is correct here, not per-IP tracking.
"""
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from companion_robot.storage.migrations import run_migrations


class RateLimiter:
    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 300) -> None:
        self._max_attempts = max_attempts
        self._lockout_seconds = lockout_seconds
        self._failed_attempts = 0
        self._locked_until: float | None = None

    def is_locked_out(self) -> bool:
        if self._locked_until is None:
            return False
        if time.monotonic() >= self._locked_until:
            self._failed_attempts = 0
            self._locked_until = None
            return False
        return True

    def record_failure(self) -> None:
        self._failed_attempts += 1
        if self._failed_attempts >= self._max_attempts:
            self._locked_until = time.monotonic() + self._lockout_seconds

    def record_success(self) -> None:
        self._failed_attempts = 0
        self._locked_until = None

    def seconds_remaining(self) -> int:
        if self._locked_until is None:
            return 0
        return max(0, int(self._locked_until - time.monotonic()))


class PinRepository:
    """Single-row settings table (id=1 enforced by CHECK) -- one PIN
    per device, not a multi-user account system."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        run_migrations(conn)

    def is_set(self) -> bool:
        row = self._conn.execute("SELECT 1 FROM parent_pin WHERE id = 1").fetchone()
        return row is not None

    def set_pin(self, pin: str) -> None:
        pin_hash = generate_password_hash(pin)
        self._conn.execute(
            "INSERT INTO parent_pin (id, pin_hash, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET pin_hash = excluded.pin_hash, "
            "updated_at = excluded.updated_at",
            (pin_hash, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def verify(self, pin: str) -> bool:
        row = self._conn.execute("SELECT pin_hash FROM parent_pin WHERE id = 1").fetchone()
        if row is None:
            return False
        return check_password_hash(row["pin_hash"], pin)


def load_or_create_secret_key(path: str | Path) -> bytes:
    """Flask session cookies are signed with this -- must be random and
    persisted across restarts, never hardcoded (a fixed key would let
    anyone forge a logged-in session)."""
    path = Path(path)
    if path.exists():
        return path.read_bytes()
    key = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key)
    return key
