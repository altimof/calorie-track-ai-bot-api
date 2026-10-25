import uuid
from typing import Any

from .. import database


async def db_get_goal(user_id: str) -> dict[str, Any] | None:
    """Get user's goal."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM goals WHERE user_id = %s", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_create_or_update_goal(user_id: str, daily_kcal_target: int) -> dict[str, Any]:
    """Create or update user's goal."""
    pool = await database.get_pool()

    existing = await db_get_goal(user_id)

    async with pool.connection() as conn:
        if existing:
            cur = await conn.execute(
                "UPDATE goals SET daily_kcal_target = %s, updated_at = NOW() WHERE id = %s RETURNING *",
                (daily_kcal_target, existing["id"]),
            )
            row = await cur.fetchone()
            if row:
                return dict(row)

        # Create new goal
        goal_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO goals (id, user_id, daily_kcal_target) VALUES (%s, %s, %s)",
            (goal_id, user_id, daily_kcal_target),
        )
        return {"id": goal_id, "user_id": user_id, "daily_kcal_target": daily_kcal_target}
