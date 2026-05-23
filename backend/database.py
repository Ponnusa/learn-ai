"""
Database connection pool — Neon PostgreSQL via asyncpg.
"""
import asyncpg
from contextlib import asynccontextmanager
from config import settings

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
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
