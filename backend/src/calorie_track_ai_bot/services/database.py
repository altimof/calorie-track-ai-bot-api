"""Async PostgreSQL connection pool using psycopg3.

Provides a shared connection pool for all database operations.
Uses dict_row factory so query results are returned as dicts.
"""

import os

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import logger

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    """Get or create the async connection pool."""
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=2,
            max_size=10,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": 10,
                # Detect connections silently dropped by the network/pooler (e.g. after
                # this process was suspended) instead of hanging forever on recv().
                "keepalives": 1,
                "keepalives_idle": 10,
                "keepalives_interval": 5,
                "keepalives_count": 3,
            },
            check=AsyncConnectionPool.check_connection,
            max_idle=300,
        )
        await _pool.open()
        logger.info("Database connection pool opened")
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
