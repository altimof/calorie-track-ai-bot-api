import uuid
from typing import Any

from psycopg.types.json import Json

from .. import database


async def db_save_estimate(
    photo_id: str,
    est: dict[str, Any],
    photo_ids: list[str] | None = None,
    estimate_id: str | None = None,
) -> str:
    """Save an estimate under estimate_id (the ID handed out at enqueue), or a new UUID."""
    pool = await database.get_pool()

    eid = estimate_id or str(uuid.uuid4())

    # Build columns and values dynamically
    columns = [
        "id",
        "photo_id",
        "kcal_mean",
        "kcal_min",
        "kcal_max",
        "confidence",
        "items",
        "status",
        "macronutrients",
        "photo_count",
    ]
    values: list[Any] = [
        eid,
        photo_id,
        est.get("kcal_mean"),
        est.get("kcal_min"),
        est.get("kcal_max"),
        est.get("confidence"),
        Json(est["items"]) if est.get("items") is not None else None,
        est.get("status", "done"),
        Json(est["macronutrients"]) if est.get("macronutrients") is not None else None,
        est.get("photo_count"),
    ]

    if photo_ids:
        columns.append("photo_ids")
        values.append(photo_ids)

    placeholders = ", ".join(["%s"] * len(values))
    col_names = ", ".join(columns)

    async with pool.connection() as conn:
        await conn.execute(
            f"INSERT INTO estimates ({col_names}) VALUES ({placeholders})",  # type: ignore[arg-type]
            tuple(values),
        )

    return eid


async def db_get_estimate(estimate_id: str) -> dict[str, Any] | None:
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM estimates WHERE id = %s", (estimate_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_get_user_estimate(estimate_id: str, user_id: str) -> dict[str, Any] | None:
    """Get an estimate by ID only if one of its photos belongs to the given user."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        # Look the estimate's photos up by primary key (photo_ids holds photo UUIDs as
        # text); matching on user_id first would scan all of the user's photos.
        cur = await conn.execute(
            """SELECT e.* FROM estimates e
               WHERE e.id = %s
                 AND EXISTS (
                   SELECT 1 FROM photos p
                   WHERE p.id = ANY(array_append(e.photo_ids::uuid[], e.photo_id))
                     AND p.user_id = %s
                 )""",
            (estimate_id, user_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
