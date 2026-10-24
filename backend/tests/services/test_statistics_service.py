"""Tests for the macro breakdown in StatisticsService."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from calorie_track_ai_bot.services.statistics_service import StatisticsService

USER_ID = "1d882190-ac3f-4a06-8a44-20e46bafb9a5"


def meal(kcal: float, protein: float, fat: float, carbs: float) -> dict:
    return {"kcal_total": kcal, "protein_grams": protein, "fats_grams": fat, "carbs_grams": carbs}


@pytest.fixture
def meals_query():
    """Patch the pool so the meals query returns the rows a test sets."""
    cursor = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=cursor)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = ctx

    with patch(
        "calorie_track_ai_bot.services.statistics_service.get_pool",
        AsyncMock(return_value=pool),
    ):
        yield cursor


async def macro_stats():
    return await StatisticsService().get_macro_statistics(
        USER_ID, date(2026, 10, 5), date(2026, 10, 12)
    )


class TestMacroBreakdown:
    @pytest.mark.asyncio
    async def test_percentages_are_shares_of_macro_calories(self, meals_query):
        # 80g protein (320 kcal), 107g fat (963 kcal), 120g carbs (480 kcal) = 1763 kcal,
        # while the AI's kcal_total is 1745
        meals_query.fetchall.return_value = [meal(1745, 80, 107, 120)]

        result = await macro_stats()

        assert result.protein_percent == 18.15
        assert result.fat_percent == 54.62
        assert result.carbs_percent == 27.23
        total = result.protein_percent + result.fat_percent + result.carbs_percent
        assert total == pytest.approx(100, abs=0.02)
        assert result.total_calories == 1745

    @pytest.mark.asyncio
    async def test_kcal_total_below_macro_calories_stays_within_100(self, meals_query):
        # Dividing 900 fat kcal by a 500 kcal estimate used to give 180% and a 500 error
        meals_query.fetchall.return_value = [meal(500, 10, 100, 10)]

        result = await macro_stats()

        assert 0 <= result.fat_percent <= 100
        assert result.fat_percent == 91.84

    @pytest.mark.asyncio
    async def test_percentages_are_rounded_to_two_decimals(self, meals_query):
        meals_query.fetchall.return_value = [meal(700, 33.3, 11.1, 77.7)]

        result = await macro_stats()

        for value in (result.protein_percent, result.fat_percent, result.carbs_percent):
            assert value == round(value, 2)

    @pytest.mark.asyncio
    async def test_no_macros_gives_zero_percentages(self, meals_query):
        meals_query.fetchall.return_value = [meal(300, 0, 0, 0)]

        result = await macro_stats()

        assert (result.protein_percent, result.fat_percent, result.carbs_percent) == (0, 0, 0)

    @pytest.mark.asyncio
    async def test_no_meals(self, meals_query):
        meals_query.fetchall.return_value = []

        result = await macro_stats()

        assert result.total_calories == 0
        assert result.protein_percent == 0
