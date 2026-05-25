"""
Database connection pool — Neon PostgreSQL via asyncpg.
"""
import json
import asyncpg
from contextlib import asynccontextmanager
from config import settings

_pool: asyncpg.Pool | None = None


async def _register_codecs(conn: asyncpg.Connection) -> None:
    """
    Register JSON/JSONB codecs on every new connection so asyncpg
    automatically decodes JSONB columns to Python dicts/lists.

    Without this, asyncpg returns JSONB as raw JSON strings and callers
    must call json.loads() manually — an error-prone pattern that caused
    quiz pages to crash and chat metadata to be silently lost.

    Note: we still pass json.dumps() strings for JSONB parameters in SQL
    (e.g. ``$1::jsonb``). asyncpg sends those as the ``text`` OID (25),
    not the ``jsonb`` OID (3802), so the encoder below is never called
    for those writes — PostgreSQL handles the cast itself.
    """
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
        init=_register_codecs,   # applied to every connection on creation
    )


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")
    return _pool


@asynccontextmanager
async def get_db():
    """Async context manager yielding a single connection from the pool."""
    async with get_pool().acquire() as conn:
        yield conn
