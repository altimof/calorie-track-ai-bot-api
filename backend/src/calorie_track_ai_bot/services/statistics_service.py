"""Statistics Service - Nutrition data aggregation and analytics.

Feature: 005-mini-app-improvements
Provides real-time aggregation of nutrition statistics for visualization.
"""

from datetime import date

from ..schemas import (
    DailyDataPoint,
    DailyStatisticsResponse,
    MacroStatisticsResponse,
    StatisticsPeriod,
    StatisticsSummary,
)
from .config import logger
from .database import get_pool
from .db._base import LOCAL_MEAL_DATE_SQL


class StatisticsService:
    """Service for aggregating and computing nutrition statistics."""

    async def get_daily_statistics(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        tz: str = "UTC",
    ) -> DailyStatisticsResponse:
        """Get daily nutrition statistics for a date range.

        Meals are grouped by their calendar day in the ``tz`` time zone; ``end_date``
        is exclusive.
        """
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")

        if (end_date - start_date).days > 365:
            raise ValueError("Date range cannot exceed 365 days")

        try:
            pool = await get_pool()

            async with pool.connection() as conn:
                cur = await conn.execute(
                    f"""SELECT {LOCAL_MEAL_DATE_SQL} AS meal_date,
                              coalesce(sum(kcal_total), 0) AS total_calories,
                              coalesce(sum(protein_grams), 0) AS total_protein,
                              coalesce(sum(fats_grams), 0) AS total_fat,
                              coalesce(sum(carbs_grams), 0) AS total_carbs,
                              count(*) AS meal_count
                       FROM meals
                       WHERE user_id = %s
                         AND {LOCAL_MEAL_DATE_SQL} >= %s AND {LOCAL_MEAL_DATE_SQL} < %s
                       GROUP BY 1
                       ORDER BY 1""",  # type: ignore[arg-type]
                    (tz, user_id, tz, start_date, tz, end_date),
                )
                daily_data = [dict(r) for r in await cur.fetchall()]

                # Get user's goal (one per user, enforced by idx_goals_user_id_unique)
                cur = await conn.execute(
                    "SELECT daily_kcal_target FROM goals WHERE user_id = %s",
                    (user_id,),
                )
                goal_row = await cur.fetchone()
                goal_calories = dict(goal_row)["daily_kcal_target"] if goal_row else None

            # Convert to data points
            data_points = []
            for day in daily_data:
                goal_achievement = None
                if goal_calories and goal_calories > 0:
                    goal_achievement = (float(day["total_calories"]) / float(goal_calories)) * 100

                data_points.append(
                    DailyDataPoint(
                        date=date.fromisoformat(day["meal_date"])
                        if isinstance(day["meal_date"], str)
                        else day["meal_date"],
                        total_calories=float(day["total_calories"]),
                        total_protein=float(day["total_protein"]),
                        total_fat=float(day["total_fat"]),
                        total_carbs=float(day["total_carbs"]),
                        meal_count=int(day["meal_count"]),
                        goal_calories=float(goal_calories) if goal_calories else None,
                        goal_achievement=goal_achievement,
                    )
                )

            total_days = (end_date - start_date).days
            total_meals = sum(dp.meal_count for dp in data_points)
            total_calories = sum(dp.total_calories for dp in data_points)
            average_daily_calories = total_calories / total_days if total_days > 0 else 0

            average_goal_achievement = None
            if goal_calories:
                achievements = [
                    dp.goal_achievement for dp in data_points if dp.goal_achievement is not None
                ]
                average_goal_achievement = (
                    sum(achievements) / len(achievements) if achievements else 0
                )

            period = StatisticsPeriod(
                start_date=start_date,
                end_date=end_date,
                total_days=total_days,
            )

            summary = StatisticsSummary(
                total_meals=total_meals,
                average_daily_calories=average_daily_calories,
                average_goal_achievement=average_goal_achievement,
            )

            return DailyStatisticsResponse(data=data_points, period=period, summary=summary)

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to retrieve daily statistics: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_macro_statistics(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        tz: str = "UTC",
    ) -> MacroStatisticsResponse:
        """Get macronutrient breakdown for a date range.

        Dates are calendar days in the ``tz`` time zone; ``end_date`` is exclusive.
        """
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")

        if (end_date - start_date).days > 365:
            raise ValueError("Date range cannot exceed 365 days")

        try:
            pool = await get_pool()

            async with pool.connection() as conn:
                cur = await conn.execute(
                    f"""SELECT kcal_total, protein_grams, fats_grams, carbs_grams
                       FROM meals
                       WHERE user_id = %s
                         AND {LOCAL_MEAL_DATE_SQL} >= %s AND {LOCAL_MEAL_DATE_SQL} < %s""",  # type: ignore[arg-type]
                    (user_id, tz, start_date, tz, end_date),
                )
                rows = [dict(r) for r in await cur.fetchall()]

            total_protein = sum(float(m.get("protein_grams", 0) or 0) for m in rows)
            total_fat = sum(float(m.get("fats_grams", 0) or 0) for m in rows)
            total_carbs = sum(float(m.get("carbs_grams", 0) or 0) for m in rows)
            total_calories = sum(float(m.get("kcal_total", 0) or 0) for m in rows)

            protein_percent = 0.0
            fat_percent = 0.0
            carbs_percent = 0.0

            if total_calories > 0:
                protein_percent = (total_protein * 4 / total_calories) * 100
                fat_percent = (total_fat * 9 / total_calories) * 100
                carbs_percent = (total_carbs * 4 / total_calories) * 100

            period = StatisticsPeriod(
                start_date=start_date,
                end_date=end_date,
                total_days=(end_date - start_date).days,
            )

            return MacroStatisticsResponse(
                protein_percent=protein_percent,
                fat_percent=fat_percent,
                carbs_percent=carbs_percent,
                protein_grams=total_protein,
                fat_grams=total_fat,
                carbs_grams=total_carbs,
                total_calories=total_calories,
                period=period,
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to retrieve macro statistics: {e}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            raise


# Global service instance
_statistics_service: StatisticsService | None = None


def get_statistics_service() -> StatisticsService:
    """Get the global statistics service instance."""
    global _statistics_service
    if _statistics_service is None:
        _statistics_service = StatisticsService()
    return _statistics_service
