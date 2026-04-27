import os, asyncpg, logging
from typing import AsyncGenerator

log = logging.getLogger("aminra.auth.db")

_pool: asyncpg.Pool | None = None


def _pool_config() -> dict:
    """Read pool sizing from env so we can tune per-deployment without code change.

    Defaults are conservative; production should set DB_POOL_MAX_SIZE >= 4*CPU.
    """
    return {
        "min_size":         int(os.getenv("DB_POOL_MIN_SIZE", "2")),
        "max_size":         int(os.getenv("DB_POOL_MAX_SIZE", "10")),
        "max_queries":      int(os.getenv("DB_POOL_MAX_QUERIES", "50000")),
        "max_inactive_connection_lifetime": float(
            os.getenv("DB_POOL_INACTIVE_LIFETIME", "300")
        ),
        "command_timeout":  float(os.getenv("DB_COMMAND_TIMEOUT", "30")),
    }


async def init_pool():
    global _pool
    url = os.getenv("DATABASE_URL")
    if not url:
        log.warning("DATABASE_URL not set — auth DB disabled")
        return
    try:
        cfg = _pool_config()
        _pool = await asyncpg.create_pool(url, **cfg)
        log.info("PostgreSQL pool ready: min=%d max=%d", cfg["min_size"], cfg["max_size"])
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
