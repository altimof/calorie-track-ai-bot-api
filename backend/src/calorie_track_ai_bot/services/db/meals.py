import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ...schemas import (
    Macronutrients,
    MealCalendarDay,
    MealCreateFromEstimateRequest,
    MealCreateManualRequest,
    MealPhotoInfo,
    MealWithPhotos,
)
from .. import database
from ..config import logger
from ..storage import BUCKET_NAME, s3
from ._base import LOCAL_MEAL_DATE_SQL, resolve_user_id
from .estimates import db_get_estimate, db_get_user_estimate
from .photos import db_get_photo


async def db_create_meal_from_manual(data: MealCreateManualRequest) -> dict[str, str]:
    pool = await database.get_pool()

    mid = str(uuid.uuid4())
    async with pool.connection() as conn:
        await conn.execute(
            """INSERT INTO meals (id, user_id, meal_date, meal_type, kcal_total, source)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (mid, None, data.meal_date, data.meal_type.value, data.kcal_total, "manual"),
        )
    return {"meal_id": mid}


async def db_create_meal_from_estimate(
    data: MealCreateFromEstimateRequest, user_id: str
) -> dict[str, str]:
    pool = await database.get_pool()

    mid = str(uuid.uuid4())

    # Get the estimate data to retrieve kcal_mean; only the owner of its photos may use it
    estimate = await db_get_user_estimate(str(data.estimate_id), user_id)
    if not estimate:
        raise ValueError(f"Estimate not found: {data.estimate_id}")

    # Set kcal_total from estimate unless overridden
    kcal_total = estimate.get("kcal_mean", 0)
    if data.overrides:
        kcal_total = data.overrides.get("kcal_total", kcal_total)

    # Extract macronutrients from estimate
    macronutrients = estimate.get("macronutrients") or {}
    protein_grams = macronutrients.get("protein", 0)
    carbs_grams = macronutrients.get("carbs", 0)
    fats_grams = macronutrients.get("fats", 0)

    # Apply overrides if provided
    if data.overrides:
        protein_grams = data.overrides.get("protein_grams", protein_grams)
        carbs_grams = data.overrides.get("carbs_grams", carbs_grams)
        fats_grams = data.overrides.get("fats_grams", fats_grams)

    async with pool.connection() as conn:
        await conn.execute(
            """INSERT INTO meals (id, user_id, meal_date, meal_type, kcal_total,
                                  protein_grams, carbs_grams, fats_grams, source, estimate_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                mid,
                user_id,
                data.meal_date,
                data.meal_type.value,
                kcal_total,
                protein_grams,
                carbs_grams,
                fats_grams,
                "photo",
                data.estimate_id,
            ),
        )

        # Link photos to the meal
        photo_ids = estimate.get("photo_ids") or []
        if not photo_ids:
            single_photo_id = estimate.get("photo_id")
            if single_photo_id:
                photo_ids = [str(single_photo_id)]

        for i, photo_id in enumerate(photo_ids[:5]):
            await conn.execute(
                "UPDATE photos SET meal_id = %s, display_order = %s WHERE id = %s AND user_id = %s",
                (mid, i, photo_id, user_id),
            )

        if photo_ids:
            logger.info(f"Linked {len(photo_ids)} photos to meal {mid}")
        else:
            logger.warning(f"No photo_ids found in estimate {data.estimate_id}")

    return {"meal_id": mid}


def _generate_meal_description(estimate: dict[str, Any]) -> str:
    """Generate a meal description from AI estimate items."""
    if not estimate or "items" not in estimate:
        return "No description available"

    items = estimate["items"]
    if not items or not isinstance(items, list):
        return "No description available"

    descriptions = []
    for item in items:
        if isinstance(item, dict) and "label" in item:
            descriptions.append(item["label"])

    if descriptions:
        if len(descriptions) == 1:
            return descriptions[0]
        elif len(descriptions) == 2:
            return f"{descriptions[0]} and {descriptions[1]}"
        else:
            return f"{', '.join(descriptions[:-1])}, and {descriptions[-1]}"

    return "No description available"


def _ensure_updated_at(meal: dict[str, Any]) -> None:
    """Set updated_at fallback from created_at or current time."""
    if "updated_at" not in meal and "created_at" in meal:
        meal["updated_at"] = meal["created_at"]
    elif "updated_at" not in meal:
        now = datetime.now(UTC).isoformat()
        meal["created_at"] = now
        meal["updated_at"] = now


async def _enhance_meal_with_related_data(meal: dict[str, Any]) -> None:
    """Enhance meal data with related estimate and photo information."""
    if not meal.get("estimate_id"):
        if "macros" not in meal:
            meal["macros"] = {"protein_g": 0, "fat_g": 0, "carbs_g": 0}
        if "description" not in meal:
            meal["description"] = "Manual entry"
        if "corrected" not in meal:
            meal["corrected"] = False
        _ensure_updated_at(meal)
        return

    estimate = await db_get_estimate(str(meal["estimate_id"]))
    if not estimate:
        logger.warning(f"Estimate {meal['estimate_id']} not found for meal {meal['id']}")
        meal["photo_url"] = None
        meal["macros"] = {"protein_g": 0, "fat_g": 0, "carbs_g": 0}
        meal["corrected"] = False
        _ensure_updated_at(meal)
        return

    photo = await db_get_photo(str(estimate["photo_id"]))
    if photo and s3:
        try:
            photo_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET_NAME, "Key": photo["tigris_key"]},
                ExpiresIn=3600,
            )
            meal["photo_url"] = photo_url
        except Exception as e:
            logger.warning(f"Failed to generate photo URL for meal {meal['id']}: {e}")
            meal["photo_url"] = None
    else:
        meal["photo_url"] = None

    meal["macros"] = {
        "protein_g": meal.get("protein_grams", 0) or 0,
        "fat_g": meal.get("fats_grams", 0) or 0,
        "carbs_g": meal.get("carbs_grams", 0) or 0,
    }
    meal["description"] = _generate_meal_description(estimate)
    meal["corrected"] = False
    _ensure_updated_at(meal)


async def db_get_meals_by_date(
    meal_date: str, telegram_user_id: str | None = None
) -> list[dict[str, Any]]:
    """Get meals for a specific date with related data."""
    pool = await database.get_pool()

    user_id = await resolve_user_id(telegram_user_id)

    async with pool.connection() as conn:
        if user_id:
            cur = await conn.execute(
                "SELECT * FROM meals WHERE meal_date = %s AND user_id = %s",
                (meal_date, user_id),
            )
        else:
            cur = await conn.execute("SELECT * FROM meals WHERE meal_date = %s", (meal_date,))
        rows = await cur.fetchall()
        meals = [dict(r) for r in rows]

    for meal in meals:
        await _enhance_meal_with_related_data(meal)

    return meals


async def db_get_meal(meal_id: str) -> dict[str, Any] | None:
    """Get a specific meal by ID with related data."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM meals WHERE id = %s", (meal_id,))
        row = await cur.fetchone()

    if not row:
        return None

    meal = dict(row)
    await _enhance_meal_with_related_data(meal)
    return meal


async def db_update_meal(meal_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a meal with the given updates."""
    pool = await database.get_pool()

    if not updates:
        return None

    set_clauses = []
    values: list[Any] = []
    for key, val in updates.items():
        set_clauses.append(f"{key} = %s")
        values.append(val)
    values.append(meal_id)

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"UPDATE meals SET {', '.join(set_clauses)} WHERE id = %s RETURNING *",
            tuple(values),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def db_delete_meal(meal_id: str) -> bool:
    """Delete a meal by ID, unlinking its photos first.

    The photos.meal_id foreign key has no ON DELETE action, so linked photos must be
    detached in the same transaction or the delete is rejected.
    """
    pool = await database.get_pool()

    async with pool.connection() as conn:
        await conn.execute("UPDATE photos SET meal_id = NULL WHERE meal_id = %s", (meal_id,))
        cur = await conn.execute("DELETE FROM meals WHERE id = %s RETURNING id", (meal_id,))
        row = await cur.fetchone()
        return row is not None


def _build_meal_photo_info(photo: dict[str, Any], meal_id: Any) -> MealPhotoInfo:
    """Convert a photo row to MealPhotoInfo with presigned URLs."""
    from ..storage import generate_presigned_url

    try:
        url = generate_presigned_url(photo["tigris_key"], expiry=3600)
        return MealPhotoInfo(
            id=photo["id"],
            thumbnailUrl=url,
            fullUrl=url,
            displayOrder=photo["display_order"],
        )
    except Exception as e:
        logger.warning(f"Failed to generate photo URLs for meal {meal_id}: {e}")
        return MealPhotoInfo(
            id=photo["id"],
            thumbnailUrl="",
            fullUrl="",
            displayOrder=photo["display_order"],
        )


async def db_get_meal_with_photos(meal_id: uuid.UUID) -> Any | None:
    """Get meal with associated photos and macronutrients."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM meals WHERE id = %s", (str(meal_id),))
        meal_data = await cur.fetchone()
        if not meal_data:
            return None
        meal_data = dict(meal_data)

        cur = await conn.execute(
            """SELECT id, tigris_key, display_order FROM photos
               WHERE meal_id = %s ORDER BY display_order""",
            (str(meal_id),),
        )
        photo_rows: list[dict[str, Any]] = [dict(r) for r in await cur.fetchall()]

    photos = [_build_meal_photo_info(photo, meal_id) for photo in photo_rows]

    macros = Macronutrients(
        protein=meal_data.get("protein_grams", 0) or 0,
        carbs=meal_data.get("carbs_grams", 0) or 0,
        fats=meal_data.get("fats_grams", 0) or 0,
    )

    return MealWithPhotos(
        id=meal_data["id"],
        userId=meal_data["user_id"],
        createdAt=meal_data["created_at"],
        description=meal_data.get("description"),
        calories=meal_data.get("kcal_total", 0),
        macronutrients=macros,
        photos=photos,
        confidenceScore=meal_data.get("confidence_score"),
    )


async def db_get_meals_with_photos(
    user_id: uuid.UUID,
    query_date: Any | None = None,
    start_date: Any | None = None,
    end_date: Any | None = None,
    limit: int = 50,
    tz: str = "UTC",
) -> list[Any]:
    """Get meals with photos for date/range (filters meals older than 1 year).

    Dates are calendar days in the ``tz`` time zone.
    """
    pool = await database.get_pool()

    from datetime import date as date_type

    one_year_ago = (date_type.today() - timedelta(days=365)).isoformat()

    # Build query
    conditions = ["user_id = %s", "created_at >= %s"]
    params: list[Any] = [str(user_id), one_year_ago]

    if query_date:
        conditions.append(f"{LOCAL_MEAL_DATE_SQL} = %s")
        params.extend([tz, query_date])
    elif start_date and end_date:
        conditions.append(f"{LOCAL_MEAL_DATE_SQL} BETWEEN %s AND %s")
        params.extend([tz, start_date, end_date])

    where = " AND ".join(conditions)
    params.append(limit)

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"SELECT * FROM meals WHERE {where} ORDER BY created_at DESC LIMIT %s",  # type: ignore[arg-type]
            tuple(params),
        )
        meals_data: list[dict[str, Any]] = [dict(r) for r in await cur.fetchall()]

        if not meals_data:
            return []

        meal_ids = [str(m["id"]) for m in meals_data]

        cur = await conn.execute(
            """SELECT id, tigris_key, display_order, meal_id FROM photos
               WHERE meal_id = ANY(%s) ORDER BY display_order""",
            (meal_ids,),
        )
        photos_data: list[dict[str, Any]] = [dict(r) for r in await cur.fetchall()]

        # Batch fetch estimates
        estimate_ids = [
            str(m["estimate_id"])
            for m in meals_data
            if m.get("estimate_id") and not m.get("description")
        ]

        estimates_by_id: dict[str, dict[str, Any]] = {}
        if estimate_ids:
            cur = await conn.execute("SELECT * FROM estimates WHERE id = ANY(%s)", (estimate_ids,))
            estimates_by_id = {str(e["id"]): e for e in (dict(r) for r in await cur.fetchall())}

    # Group photos by meal_id
    photos_by_meal: dict[str, list[dict[str, Any]]] = {}
    for photo in photos_data:
        mid = str(photo["meal_id"])
        if mid not in photos_by_meal:
            photos_by_meal[mid] = []
        photos_by_meal[mid].append(photo)

    result_meals = []
    for meal_data in meals_data:
        meal_id = str(meal_data["id"])
        meal_photos = photos_by_meal.get(meal_id, [])

        photos = [_build_meal_photo_info(photo, meal_id) for photo in meal_photos]

        macros = Macronutrients(
            protein=meal_data.get("protein_grams", 0) or 0,
            carbs=meal_data.get("carbs_grams", 0) or 0,
            fats=meal_data.get("fats_grams", 0) or 0,
        )

        description = meal_data.get("description")
        if not description and meal_data.get("estimate_id"):
            estimate = estimates_by_id.get(str(meal_data["estimate_id"]))
            if estimate:
                description = _generate_meal_description(estimate)
            else:
                description = "No description available"
        elif not description:
            description = "Manual entry"

        result_meals.append(
            MealWithPhotos(
                id=meal_data["id"],
                userId=meal_data["user_id"],
                createdAt=meal_data["created_at"],
                description=description,
                calories=meal_data.get("kcal_total", 0),
                macronutrients=macros,
                photos=photos,
                confidenceScore=meal_data.get("confidence_score"),
            )
        )

    return result_meals


async def db_update_meal_with_macros(meal_id: uuid.UUID, updates: Any) -> Any | None:
    """Update meal and recalculate calories from macronutrients."""
    pool = await database.get_pool()

    try:
        update_data: dict[str, Any] = {}

        if updates.description is not None:
            update_data["description"] = updates.description
        if updates.protein_grams is not None:
            update_data["protein_grams"] = updates.protein_grams
        if updates.carbs_grams is not None:
            update_data["carbs_grams"] = updates.carbs_grams
        if updates.fats_grams is not None:
            update_data["fats_grams"] = updates.fats_grams

        # Recalculate calories if macros updated (4-4-9 formula)
        if any(k in update_data for k in ["protein_grams", "carbs_grams", "fats_grams"]):
            async with pool.connection() as conn:
                cur = await conn.execute("SELECT * FROM meals WHERE id = %s", (str(meal_id),))
                current = await cur.fetchone()

            if current:
                current = dict(current)
                protein = update_data.get("protein_grams", current.get("protein_grams", 0) or 0)
                carbs = update_data.get("carbs_grams", current.get("carbs_grams", 0) or 0)
                fats = update_data.get("fats_grams", current.get("fats_grams", 0) or 0)
                update_data["kcal_total"] = protein * 4 + carbs * 4 + fats * 9

        if not update_data:
            return None

        set_clauses = [f"{k} = %s" for k in update_data]
        values = [*list(update_data.values()), str(meal_id)]

        async with pool.connection() as conn:
            await conn.execute(
                f"UPDATE meals SET {', '.join(set_clauses)} WHERE id = %s",  # type: ignore[arg-type]
                tuple(values),
            )

        return await db_get_meal_with_photos(meal_id)

    except Exception as e:
        logger.error(f"Error updating meal with macros: {e}")
        raise


async def db_get_meals_calendar_summary(
    user_id: uuid.UUID, start_date: Any, end_date: Any, tz: str = "UTC"
) -> list[Any]:
    """Get daily meal summaries for calendar view, bucketed by calendar day in ``tz``."""
    pool = await database.get_pool()

    try:
        one_year_ago = (date.today() - timedelta(days=365)).isoformat()

        async with pool.connection() as conn:
            cur = await conn.execute(
                f"""SELECT {LOCAL_MEAL_DATE_SQL} AS local_date,
                          kcal_total, protein_grams, carbs_grams, fats_grams
                   FROM meals
                   WHERE user_id = %s AND created_at >= %s
                     AND {LOCAL_MEAL_DATE_SQL} BETWEEN %s AND %s""",  # type: ignore[arg-type]
                (tz, str(user_id), one_year_ago, tz, start_date, end_date),
            )
            rows = await cur.fetchall()

        if not rows:
            return []

        daily_data: dict[str, dict[str, float]] = {}
        for meal in rows:
            meal = dict(meal)
            meal_date = str(meal["local_date"])

            if meal_date not in daily_data:
                daily_data[meal_date] = {
                    "count": 0,
                    "calories": 0,
                    "protein": 0,
                    "carbs": 0,
                    "fats": 0,
                }

            daily_data[meal_date]["count"] += 1
            daily_data[meal_date]["calories"] += meal.get("kcal_total", 0) or 0
            daily_data[meal_date]["protein"] += meal.get("protein_grams", 0) or 0
            daily_data[meal_date]["carbs"] += meal.get("carbs_grams", 0) or 0
            daily_data[meal_date]["fats"] += meal.get("fats_grams", 0) or 0

        calendar_days = []
        for date_str, data in sorted(daily_data.items(), reverse=True):
            calendar_days.append(
                MealCalendarDay(
                    meal_date=datetime.fromisoformat(date_str).date(),
                    meal_count=int(data["count"]),
                    total_calories=data["calories"],
                    total_protein=data["protein"],
                    total_carbs=data["carbs"],
                    total_fats=data["fats"],
                )
            )

        return calendar_days

    except Exception as e:
        logger.error(f"Error getting calendar summary: {e}")
        raise
