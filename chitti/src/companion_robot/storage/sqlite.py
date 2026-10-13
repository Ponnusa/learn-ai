"""SQLite connection helper (spec section 10: SQLite for the first
local prototype, with migrations and a repository abstraction).
"""
import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
