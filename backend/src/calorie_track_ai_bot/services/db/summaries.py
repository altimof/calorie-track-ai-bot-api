from typing import Any

from .. import database
from ._base import LOCAL_MEAL_DATE_SQL

# Meals whose local calendar day (in the given time zone) equals the given date.
_ON_LOCAL_DATE = f"{LOCAL_MEAL_DATE_SQL} = %s"

# Meal columns summed into a summary; meals without macros have NULLs there.
_TOTALS_COLUMNS = "kcal_total, protein_grams, fats_grams, carbs_grams"


def _sum_meals(meals: list[dict[str, Any]]) -> tuple[float, dict[str, float]]:
    """Total calories and macronutrients of meals, counting missing values as 0."""
    kcal = 0.0
    macros = {"protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    for meal in meals:
        kcal += float(meal.get("kcal_total") or 0)
        macros["protein_g"] += float(meal.get("protein_grams") or 0)
        macros["fat_g"] += float(meal.get("fats_grams") or 0)
        macros["carbs_g"] += float(meal.get("carbs_grams") or 0)
    return kcal, macros


async def db_get_daily_summary(date: str, user_id: str, tz: str = "UTC") -> dict[str, Any] | None:
    """Get the user's daily summary for a specific calendar date in ``tz``."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"SELECT {_TOTALS_COLUMNS} FROM meals WHERE {_ON_LOCAL_DATE} AND user_id = %s",  # type: ignore[arg-type]
            (tz, date, user_id),
        )
        rows = await cur.fetchall()

    total_kcal, macro_totals = _sum_meals([dict(r) for r in rows])

    return {
        "user_id": user_id,
        "date": date,
        "kcal_total": total_kcal,
        "macros_totals": macro_totals,
    }


async def db_get_summaries_by_date_range(
    start_date: str, end_date: str, user_id: str, tz: str = "UTC"
) -> dict[str, dict[str, Any]]:
    """Get the user's summaries for an inclusive range of calendar dates in ``tz``, in one query."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""SELECT {LOCAL_MEAL_DATE_SQL} AS meal_date, {_TOTALS_COLUMNS} FROM meals
               WHERE {LOCAL_MEAL_DATE_SQL} BETWEEN %s AND %s AND user_id = %s""",  # type: ignore[arg-type]
            (tz, tz, start_date, end_date, user_id),
        )
        rows = await cur.fetchall()

    meals_by_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        meal = dict(row)
        meals_by_date.setdefault(str(meal["meal_date"]), []).append(meal)

    summaries: dict[str, dict[str, Any]] = {}
    for d, meals in meals_by_date.items():
        kcal, macros = _sum_meals(meals)
        summaries[d] = {"user_id": user_id, "date": d, "kcal_total": kcal, "macros_totals": macros}

    return summaries


async def db_get_today_data(date: str, user_id: str, tz: str = "UTC") -> dict[str, Any]:
    """Get all of the user's data for the Today page in a single query (``date`` is in ``tz``)."""
    pool = await database.get_pool()

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"SELECT * FROM meals WHERE {_ON_LOCAL_DATE} AND user_id = %s",  # type: ignore[arg-type]
            (tz, date, user_id),
        )
        rows = await cur.fetchall()

    meals = [dict(r) for r in rows]
    kcal, macros = _sum_meals(meals)
    daily_summary = {"user_id": user_id, "date": date, "kcal_total": kcal, "macros_totals": macros}

    return {"meals": meals, "daily_summary": daily_summary}
