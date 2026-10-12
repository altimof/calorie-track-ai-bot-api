import uuid
from typing import Any

from .. import database
from ..config import logger


async def db_get_or_create_user(
    telegram_id: int, handle: str | None = None, locale: str = "en"
) -> str:
    """Get existing user or create new one based on telegram_id."""
    pool = await database.get_pool()

    logger.debug(f"Looking up user with telegram_id: {telegram_id}")

    async with pool.connection() as conn:
        row = await conn.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
        result = await row.fetchone()
        user = dict(result) if result else None

        if user:
            user_id = str(user["id"])
            logger.info(f"Found existing user: {user.get('handle') or telegram_id}")
            return user_id

        # Create new user
        user_id = str(uuid.uuid4())
        logger.info(f"Creating new user: {handle or telegram_id}")
        await conn.execute(
            "INSERT INTO users (id, telegram_id, handle, locale) VALUES (%s, %s, %s, %s)",
            (user_id, telegram_id, handle, locale),
        )
        return user_id


async def db_find_user_id(telegram_id: int) -> str | None:
    """Return the internal user ID for a registered Telegram user, or None."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
        row = await cur.fetchone()
        return str(dict(row)["id"]) if row else None


async def db_get_user(user_id: str) -> dict[str, Any] | None:
    """Get user record by ID."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
