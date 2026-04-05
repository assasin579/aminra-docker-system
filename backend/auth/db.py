import os, asyncpg, logging
from typing import AsyncGenerator

log = logging.getLogger("aminra.auth.db")

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    url = os.getenv("DATABASE_URL")
    if not url:
        log.warning("DATABASE_URL not set — auth DB disabled")
        return
    try:
        _pool = await asyncpg.create_pool(url, min_size=2, max_size=10, command_timeout=30)
        log.info("PostgreSQL pool ready")
    except Exception as e:
        log.error(f"PostgreSQL connection failed: {e}")


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not available")
    return _pool


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    if _pool is None:
        raise RuntimeError("Database not available")
    async with _pool.acquire() as conn:
        yield conn
