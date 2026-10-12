"""Statistics API Endpoints - Nutrition data visualization.

Feature: 005-mini-app-improvements
Provides endpoints for retrieving aggregated nutrition statistics.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request

from ...schemas import DailyStatisticsResponse, MacroStatisticsResponse
from ...services.config import logger
from ...services.statistics_service import get_statistics_service
from ...utils.error_handling import handle_api_errors
from .deps import get_authenticated_user_id, get_user_timezone

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/daily", response_model=DailyStatisticsResponse)
@handle_api_errors("daily statistics")
async def get_daily_statistics(
    request: Request,
    start_date: date = Query(..., description="Start date (inclusive) in YYYY-MM-DD format"),  # noqa: B008
    end_date: date = Query(..., description="End date (exclusive) in YYYY-MM-DD format"),  # noqa: B008
    tz: str = Depends(get_user_timezone),
) -> DailyStatisticsResponse:
    """Get daily nutrition statistics for a date range.

    Returns aggregated nutrition data grouped by day with meal counts,
    calorie totals, macronutrient breakdowns, and goal achievement metrics.
    Data updates in real-time as meals are logged.

    Args:
        request: FastAPI request object (for auth)
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        Daily statistics response with data points and summary

    Raises:
        HTTPException: If query fails or date range invalid
    """
    user_id = await get_authenticated_user_id(request)

    statistics_service = get_statistics_service()
    response = await statistics_service.get_daily_statistics(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        tz=tz,
    )

    logger.info(
        f"Daily statistics retrieved for user {user_id}",
        extra={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "data_points": len(response.data),
        },
    )

    return response


@router.get("/macros", response_model=MacroStatisticsResponse)
@handle_api_errors("macro statistics")
async def get_macro_statistics(
    request: Request,
    start_date: date = Query(..., description="Start date (inclusive) in YYYY-MM-DD format"),  # noqa: B008
    end_date: date = Query(..., description="End date (exclusive) in YYYY-MM-DD format"),  # noqa: B008
    tz: str = Depends(get_user_timezone),
) -> MacroStatisticsResponse:
    """Get macronutrient breakdown for a date range.

    Returns aggregated macronutrient distribution showing percentage
    and gram totals for protein, fat, and carbohydrates.

    Args:
        request: FastAPI request object (for auth)
        start_date: Start date (inclusive)
        end_date: End date (exclusive)

    Returns:
        Macronutrient breakdown response

    Raises:
        HTTPException: If query fails or date range invalid
    """
    user_id = await get_authenticated_user_id(request)

    statistics_service = get_statistics_service()
    response = await statistics_service.get_macro_statistics(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        tz=tz,
    )

    logger.info(
        f"Macro statistics retrieved for user {user_id}",
        extra={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    return response
