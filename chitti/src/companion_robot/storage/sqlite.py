"""SQLite connection helper (spec section 10: SQLite for the first
local prototype, with migrations and a repository abstraction).
"""
import sqlite3
import threading
from pathlib import Path


class _MaterializedResult:
    """A pre-fetched stand-in for a sqlite3.Cursor. Rows are captured
    eagerly, while LockingConnection.execute() still holds its lock --
    not lazily on a later, unprotected `.fetchone()`/`.fetchall()` call.
    That gap was the actual bug: two cursors sharing one real sqlite3
    connection can interfere with each other's unconsumed result sets,
    so locking only the execute() call and leaving fetch calls
    unprotected didn't close the race, it just moved it. fetchone()
    advances sequentially like a real cursor; fetchall() drains
    whatever's left. rowcount is copied from the real cursor, since
    repositories check it after UPDATE/DELETE statements.
    """

    def __init__(self, rows: list, rowcount: int) -> None:
        self._rows = rows
        self._pos = 0
        self.rowcount = rowcount

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self) -> list:
        remaining = self._rows[self._pos:]
        self._pos = len(self._rows)
        return remaining


class LockingConnection:
    """Wraps a sqlite3.Connection so every execute() call -- including
    fetching its results -- is one atomic, locked operation. Delegates
    everything else straight through."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    def execute(self, *args, **kwargs) -> _MaterializedResult:
        with self._lock:
            cursor = self._conn.execute(*args, **kwargs)
            rows = cursor.fetchall()
            return _MaterializedResult(rows, cursor.rowcount)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def connect(db_path: str | Path) -> LockingConnection:
    """check_same_thread=False: sqlite3 refuses by default to let a
    connection be used from any thread but the one that created it --
    confirmed as a real `ProgrammingError` running the Parent Controls
    web UI for real (decision 0014's manual test), since Flask's dev
    server handles different requests on different threads while the
    connection is created once, in main(), before the server starts.

    This is a deliberate, scoped tradeoff: SQLite's own file-level
    locking already serializes writes safely even across threads/
    processes, so disabling Python's thread-affinity check is a
    reasonable fit for Chitti's actual usage pattern -- one local
    device, one admin, low-frequency requests -- not a general license
    for heavy concurrent access. LockingConnection adds a Python-level
    lock around each full execute-and-fetch so overlapping requests
    can't interleave mid-statement.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return LockingConnection(conn)
