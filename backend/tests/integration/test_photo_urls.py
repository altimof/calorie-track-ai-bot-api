"""
Integration tests for photo URL generation and display functionality.
Tests the backend photo URL generation and meal data enhancement.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from calorie_track_ai_bot.schemas import MealCreateFromEstimateRequest, MealType
from calorie_track_ai_bot.services.db import (
    _enhance_meal_with_related_data,
    db_create_meal_from_estimate,
    db_get_meal,
)


def _make_mock_pool():
    """Create a mock pool with async context manager for connection."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.connection.return_value = ctx
    return mock_pool, mock_conn, mock_cursor


class TestPhotoUrlGeneration:
    """Test photo URL generation in database operations."""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client for photo URL generation."""
        mock_s3 = Mock()
        mock_s3.generate_presigned_url = Mock(return_value="https://presigned-url.example.com")
        return mock_s3

    @pytest.fixture
    def mock_db_operations(self):
        """Mock database operations for testing."""
        mock_pool, mock_conn, mock_cursor = _make_mock_pool()

        with (
            patch(
                "calorie_track_ai_bot.services.database.get_pool",
                new_callable=AsyncMock,
                return_value=mock_pool,
            ),
            patch("calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
            patch(
                "calorie_track_ai_bot.services.db.meals.db_get_estimate", new_callable=AsyncMock
            ) as mock_get_estimate,
            patch(
                "calorie_track_ai_bot.services.db.meals.db_get_photo", new_callable=AsyncMock
            ) as mock_get_photo,
            patch("calorie_track_ai_bot.services.db.meals.s3") as mock_s3,
        ):
            # Setup mock database responses
            mock_meal_data = {
                "id": "meal-uuid-123",
                "user_id": "user-uuid-123",
                "meal_date": "2025-01-27",
                "meal_type": "snack",
                "kcal_total": 650,
                "estimate_id": "estimate-uuid-123",
                "created_at": "2025-01-27T10:00:00Z",
            }

            # For db_get_meal: fetchone returns one row
            mock_cursor.fetchone = AsyncMock(return_value=mock_meal_data)
            # For list queries: fetchall returns list
            mock_cursor.fetchall = AsyncMock(return_value=[mock_meal_data])

            mock_resolve.return_value = "user-uuid-123"
            mock_get_estimate.return_value = {
                "id": "00000000-0000-0000-0000-000000000123",
                "photo_id": "photo-uuid-123",
                "kcal_mean": 650,
                "breakdown": [{"label": "chicken breast", "kcal": 300}],
            }
            mock_get_photo.return_value = {
                "id": "photo-uuid-123",
                "tigris_key": "photos/test123.jpg",
                "user_id": "user-uuid-123",
                "status": "uploaded",
            }
            mock_s3.generate_presigned_url.return_value = "https://photos.example.com/test123.jpg"

            yield {
                "pool": mock_pool,
                "conn": mock_conn,
                "cursor": mock_cursor,
                "resolve": mock_resolve,
                "get_estimate": mock_get_estimate,
                "get_photo": mock_get_photo,
                "s3": mock_s3,
            }

    @pytest.mark.asyncio
    async def test_enhance_meal_with_photo_url(self, mock_db_operations):
        """Test that _enhance_meal_with_related_data adds photo_url to meals."""
        meal_data = {
            "id": "meal-uuid-123",
            "estimate_id": "estimate-uuid-123",
            "kcal_total": 650,
            "created_at": "2025-01-27T10:00:00Z",
        }

        await _enhance_meal_with_related_data(meal_data)

        assert "photo_url" in meal_data
        assert meal_data["photo_url"] == "https://photos.example.com/test123.jpg"
        assert "macros" in meal_data
        assert meal_data["macros"] == {"protein_g": 0, "fat_g": 0, "carbs_g": 0}
        assert "corrected" in meal_data
        assert meal_data["corrected"] is False
        assert "updated_at" in meal_data

    @pytest.mark.asyncio
    async def test_enhance_meal_without_estimate(self, mock_db_operations):
        """Test meal enhancement when no estimate exists."""
        meal_data = {
            "id": "meal-uuid-123",
            "kcal_total": 500,
            "created_at": "2025-01-27T10:00:00Z",
            # No estimate_id
        }

        await _enhance_meal_with_related_data(meal_data)

        assert meal_data.get("photo_url") is None
        assert meal_data["macros"] == {"protein_g": 0, "fat_g": 0, "carbs_g": 0}
        assert meal_data["corrected"] is False
        assert "updated_at" in meal_data

    @pytest.mark.asyncio
    async def test_enhance_meal_without_updated_at(self, mock_db_operations):
        """Test meal enhancement when updated_at is missing."""
        meal_data = {
            "id": "meal-uuid-123",
            "estimate_id": "estimate-uuid-123",
            "kcal_total": 650,
            "created_at": "2025-01-27T10:00:00Z",
            # No updated_at
        }

        await _enhance_meal_with_related_data(meal_data)

        assert meal_data["updated_at"] == meal_data["created_at"]

    @pytest.mark.asyncio
    async def test_enhance_meal_missing_timestamps(self, mock_db_operations):
        """Test meal enhancement when both timestamps are missing."""
        meal_data = {
            "id": "meal-uuid-123",
            "estimate_id": "estimate-uuid-123",
            "kcal_total": 650,
            # No timestamps
        }

        await _enhance_meal_with_related_data(meal_data)

        assert "created_at" in meal_data
        assert "updated_at" in meal_data
        # Both should be recent timestamps
        assert meal_data["created_at"] == meal_data["updated_at"]

    @pytest.mark.asyncio
    async def test_photo_url_generation_error_handling(self, mock_db_operations):
        """Test error handling when photo URL generation fails."""
        # Make S3 URL generation fail
        mock_db_operations["s3"].generate_presigned_url.side_effect = Exception("S3 Error")

        meal_data = {
            "id": "meal-uuid-123",
            "estimate_id": "estimate-uuid-123",
            "kcal_total": 650,
            "created_at": "2025-01-27T10:00:00Z",
        }

        await _enhance_meal_with_related_data(meal_data)

        # Should gracefully handle the error and set photo_url to None
        assert meal_data["photo_url"] is None
        # Other fields should still be populated
        assert "macros" in meal_data
        assert "corrected" in meal_data

    @pytest.mark.asyncio
    async def test_get_meal_includes_photo_url(self, mock_db_operations):
        """Test that db_get_meal returns meals with photo URLs."""
        meal = await db_get_meal("meal-uuid-123")

        assert meal is not None
        assert "photo_url" in meal
        assert meal["photo_url"] == "https://photos.example.com/test123.jpg"
        assert "macros" in meal
        assert "corrected" in meal

    @pytest.mark.asyncio
    async def test_create_meal_from_estimate_with_kcal_from_estimate(self):
        """Test that meals created from estimates get kcal_total from estimate.kcal_mean."""
        mock_pool, mock_conn, _mock_cursor = _make_mock_pool()

        with (
            patch(
                "calorie_track_ai_bot.services.database.get_pool",
                new_callable=AsyncMock,
                return_value=mock_pool,
            ),
            patch(
                "calorie_track_ai_bot.services.db.meals.db_get_user_estimate",
                new_callable=AsyncMock,
            ) as mock_get_estimate,
        ):
            mock_get_estimate.return_value = {
                "id": "00000000-0000-0000-0000-000000000123",
                "kcal_mean": 850,
                "breakdown": [{"label": "test food", "kcal": 850}],
            }

            meal_request = MealCreateFromEstimateRequest(
                estimate_id="00000000-0000-0000-0000-000000000123",
                meal_date=date.today(),
                meal_type=MealType.snack,
            )

            await db_create_meal_from_estimate(meal_request, "telegram-user-123")

            # Verify the INSERT was called with correct kcal_total
            call_args = mock_conn.execute.call_args_list[0]
            params = call_args[0][1]
            # params: (mid, user_id, meal_date, meal_type, kcal_total, ...)
            assert params[4] == 850  # kcal_total from estimate
            assert params[3] == "snack"  # meal_type

    @pytest.mark.asyncio
    async def test_create_meal_from_estimate_with_kcal_override(self):
        """Test that meal kcal can be overridden when creating from estimate."""
        mock_pool, mock_conn, _mock_cursor = _make_mock_pool()

        with (
            patch(
                "calorie_track_ai_bot.services.database.get_pool",
                new_callable=AsyncMock,
                return_value=mock_pool,
            ),
            patch(
                "calorie_track_ai_bot.services.db.meals.db_get_user_estimate",
                new_callable=AsyncMock,
            ) as mock_get_estimate,
        ):
            mock_get_estimate.return_value = {
                "id": "00000000-0000-0000-0000-000000000123",
                "kcal_mean": 850,
                "breakdown": [{"label": "test food", "kcal": 850}],
            }

            meal_request = MealCreateFromEstimateRequest(
                estimate_id="00000000-0000-0000-0000-000000000123",
                meal_date=date.today(),
                meal_type=MealType.snack,
                overrides={"kcal_total": 750},
            )

            await db_create_meal_from_estimate(meal_request, "telegram-user-123")

            # Verify the INSERT was called with overridden kcal_total
            call_args = mock_conn.execute.call_args_list[0]
            params = call_args[0][1]
            assert params[4] == 750  # kcal_total overridden
