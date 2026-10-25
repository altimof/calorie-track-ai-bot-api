import calendar
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...schemas import DailySummary, TodayResponse
from ...services.db import db_get_daily_summary, db_get_summaries_by_date_range, db_get_today_data
from ...utils.error_handling import handle_api_errors
from .deps import get_authenticated_user_id, get_user_timezone

router = APIRouter()


@router.get("/daily-summary/{date}", response_model=DailySummary)
@handle_api_errors("daily summary")
async def get_daily_summary(
    date: str,
    user_id: str = Depends(get_authenticated_user_id),
    tz: str = Depends(get_user_timezone),
) -> dict[str, Any]:
    """Get daily summary for a specific date."""
    summary = await db_get_daily_summary(date, user_id, tz=tz)
    if summary is None:
        # Return empty summary if no meals found
        return {
            "user_id": user_id,
            "date": date,
            "kcal_total": 0,
            "macros_totals": {"protein_g": 0, "fat_g": 0, "carbs_g": 0},
        }
    return summary


@router.get("/weekly-summary", response_model=list[DailySummary])
@handle_api_errors("weekly summary")
async def get_weekly_summary(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    user_id: str = Depends(get_authenticated_user_id),
    tz: str = Depends(get_user_timezone),
) -> list[dict[str, Any]]:
    """Get weekly summary starting from the given date."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=6)

    start_date_str = start_dt.strftime("%Y-%m-%d")
    end_date_str = end_dt.strftime("%Y-%m-%d")

    # Get all meals for the week in a single query
    summaries_dict = await db_get_summaries_by_date_range(
        start_date_str, end_date_str, user_id, tz=tz
    )

    # Build the response array with all 7 days
    summaries = []
    for i in range(7):
        current_date = start_dt + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")

        if date_str in summaries_dict:
            summaries.append(summaries_dict[date_str])
        else:
            # Create empty summary for days with no meals
            summaries.append(
                {
                    "user_id": user_id,
                    "date": date_str,
                    "kcal_total": 0,
                    "macros_totals": {"protein_g": 0, "fat_g": 0, "carbs_g": 0},
                }
            )

    return summaries


@router.get("/monthly-summary", response_model=list[DailySummary])
@handle_api_errors("monthly summary")
async def get_monthly_summary(
    year: int = Query(..., description="Year"),
    month: int = Query(..., description="Month (1-12)"),
    user_id: str = Depends(get_authenticated_user_id),
    tz: str = Depends(get_user_timezone),
):
    """Get monthly summary for the given year and month."""
    # Get number of days in the month
    days_in_month = calendar.monthrange(year, month)[1]

    start_date_str = f"{year}-{month:02d}-01"
    end_date_str = f"{year}-{month:02d}-{days_in_month:02d}"

    # Get all meals for the month in a single query
    summaries_dict = await db_get_summaries_by_date_range(
        start_date_str, end_date_str, user_id, tz=tz
    )

    # Build the response array with all days of the month
    summaries = []
    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"

        if date_str in summaries_dict:
            summaries.append(summaries_dict[date_str])
        else:
            # Create empty summary for days with no meals
            summaries.append(
                {
                    "user_id": user_id,
                    "date": date_str,
                    "kcal_total": 0,
                    "macros_totals": {"protein_g": 0, "fat_g": 0, "carbs_g": 0},
                }
            )

    return summaries


@router.get("/today/{date}", response_model=TodayResponse)
@handle_api_errors("today data")
async def get_today_data(
    date: str,
    user_id: str = Depends(get_authenticated_user_id),
    tz: str = Depends(get_user_timezone),
):
    """Get all data needed for the Today page (meals + daily summary) in a single request."""
    today_data = await db_get_today_data(date, user_id, tz=tz)
    return today_data
