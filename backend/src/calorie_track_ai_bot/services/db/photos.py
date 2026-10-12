import uuid
from typing import Any

from .. import database
from ..config import logger


async def db_create_photo(
    tigris_key: str,
    user_id: str | None = None,
    display_order: int = 0,
    media_group_id: str | None = None,
) -> str:
    """Create a photo record in the database."""
    pool = await database.get_pool()

    logger.debug(
        f"Creating photo record: tigris_key={tigris_key}, user_id={user_id}, "
        f"display_order={display_order}, media_group_id={media_group_id}"
    )
    pid = str(uuid.uuid4())

    async with pool.connection() as conn:
        await conn.execute(
            """INSERT INTO photos (id, tigris_key, user_id, display_order, media_group_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (pid, tigris_key, user_id, display_order, media_group_id),
        )

    logger.info(f"Photo record created with ID: {pid}")
    return pid


async def db_get_photo(photo_id: str) -> dict[str, Any] | None:
    """Get photo record by ID."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM photos WHERE id = %s", (photo_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_get_user_photo(photo_id: str, user_id: str) -> dict[str, Any] | None:
    """Get a photo record by ID only if it belongs to the given user."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT * FROM photos WHERE id = %s AND user_id = %s", (photo_id, user_id)
        )
        row = await cur.fetchone()
        return dict(row) if row else None
