from typing import Any

from psycopg import errors

from .. import database
from ..config import logger
from ._base import resolve_user_id


async def db_get_goal(telegram_user_id: str) -> dict[str, Any] | None:
    """Get user's goal."""
    pool = await database.get_pool()

    user_id = await resolve_user_id(telegram_user_id)
    if not user_id:
        return None

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_create_or_update_goal(telegram_user_id: str, daily_kcal_target: int) -> dict[str, Any]:
    """Create or update user's goal."""
    pool = await database.get_pool()

    user_id = await resolve_user_id(telegram_user_id)
    if not user_id:
        raise ValueError(f"Could not resolve user ID for telegram_user_id: {telegram_user_id}")

    # Atomic upsert; relies on the unique index on goals(user_id)
    async with pool.connection() as conn:
        try:
            cur = await conn.execute(
                """
                INSERT INTO goals (user_id, daily_kcal_target) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET daily_kcal_target = EXCLUDED.daily_kcal_target, updated_at = NOW()
                RETURNING *
                """,
                (user_id, daily_kcal_target),
            )
        except errors.InvalidColumnReference:
            logger.error(
                "Cannot save goals: the database is missing the unique index "
                "idx_goals_user_id_unique on goals(user_id). Apply it as in backend/infra/schema.sql."
            )
            raise
        row = await cur.fetchone()
        # An upsert with RETURNING always returns the inserted or updated row
        assert row is not None
        return dict(row)
