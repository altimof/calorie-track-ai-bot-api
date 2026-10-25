"""Tests for daily summary API endpoints with user ID detection."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from calorie_track_ai_bot.api.v1.daily_summary import router

# Internal user ID the autouse registered_user fixture (conftest) resolves every
# Telegram user to; routes pass it, not the Telegram ID, to the DB layer.
INTERNAL_USER_ID = "550e8400-e29b-41d4-a716-446655440000"


class TestDailySummaryEndpoints:
    """Test daily summary-related endpoints with user ID detection."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def mock_daily_summary_data(self):
        """Sample daily summary data for testing."""
        return {
            "user_id": "59357664",
            "date": "2025-09-28",
            "kcal_total": 1500,
            "macros_totals": {
                "protein_g": 75,
                "fat_g": 50,
                "carbs_g": 150,
            },
        }

    @pytest.fixture
    def mock_today_data(self):
        """Sample today data for testing."""
        return {
            "meals": [
                {
                    "id": "meal-1",
                    "user_id": "59357664",
                    "meal_date": "2025-09-28",
                    "meal_type": "breakfast",
                    "kcal_total": 500,
                    "created_at": "2025-09-28T08:00:00Z",
                },
                {
                    "id": "meal-2",
                    "user_id": "59357664",
                    "meal_date": "2025-09-28",
                    "meal_type": "lunch",
                    "kcal_total": 700,
                    "created_at": "2025-09-28T13:00:00Z",
                },
            ],
            "daily_summary": {
                "user_id": "59357664",
                "date": "2025-09-28",
                "kcal_total": 1200,
                "macros_totals": {
                    "protein_g": 60,
                    "fat_g": 40,
                    "carbs_g": 120,
                },
            },
        }

    @patch("calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary")
    def test_get_daily_summary_with_telegram_user_id(
        self, mock_db_get_daily_summary, client, mock_daily_summary_data
    ):
        """Test getting daily summary with real Telegram user ID from header."""
        mock_db_get_daily_summary.return_value = mock_daily_summary_data

        headers = {"x-user-id": "59357664"}
        response = client.get("/daily-summary/2025-09-28", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data == mock_daily_summary_data

        # Verify that db_get_daily_summary was called with the correct parameters
        mock_db_get_daily_summary.assert_called_once_with("2025-09-28", INTERNAL_USER_ID, tz="UTC")

    def test_get_daily_summary_without_user_id_header(self, client):
        """Test getting daily summary without x-user-id header returns 401."""
        response = client.get("/daily-summary/2025-09-28")

        assert response.status_code == 401

    @patch("calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary")
    def test_get_daily_summary_no_data_found(self, mock_db_get_daily_summary, client):
        """Test getting daily summary when no data exists."""
        mock_db_get_daily_summary.return_value = None

        headers = {"x-user-id": "59357664"}
        response = client.get("/daily-summary/2025-09-28", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == INTERNAL_USER_ID
        assert data["date"] == "2025-09-28"
        assert data["kcal_total"] == 0
        assert data["macros_totals"] == {"protein_g": 0, "fat_g": 0, "carbs_g": 0}

    @patch("calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary")
    def test_get_daily_summary_database_error(self, mock_db_get_daily_summary, client):
        """Test getting daily summary when database error occurs."""
        mock_db_get_daily_summary.side_effect = Exception("Database connection failed")

        headers = {"x-user-id": "59357664"}
        response = client.get("/daily-summary/2025-09-28", headers=headers)

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    @patch("calorie_track_ai_bot.api.v1.daily_summary.db_get_today_data")
    def test_get_today_data_with_telegram_user_id(
        self, mock_db_get_today_data, client, mock_today_data
    ):
        """Test getting today data with real Telegram user ID from header."""
        mock_db_get_today_data.return_value = mock_today_data

        headers = {"x-user-id": "59357664"}
        response = client.get("/today/2025-09-28", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data == mock_today_data

        # Verify that db_get_today_data was called with the correct parameters
        mock_db_get_today_data.assert_called_once_with("2025-09-28", INTERNAL_USER_ID, tz="UTC")

    def test_get_today_data_without_user_id_header(self, client):
        """Test getting today data without x-user-id header returns 401."""
        response = client.get("/today/2025-09-28")

        assert response.status_code == 401

    @patch("calorie_track_ai_bot.api.v1.daily_summary.db_get_today_data")
    def test_get_today_data_database_error(self, mock_db_get_today_data, client):
        """Test getting today data when database error occurs."""
        mock_db_get_today_data.side_effect = Exception("Database connection failed")

        headers = {"x-user-id": "59357664"}
        response = client.get("/today/2025-09-28", headers=headers)

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    @patch("calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary")
    def test_invalid_date_format(self, mock_db_get_daily_summary, client):
        """Test getting daily summary with invalid date format."""
        mock_db_get_daily_summary.side_effect = Exception("Invalid date format")
        headers = {"x-user-id": "59357664"}
        response = client.get("/daily-summary/invalid-date", headers=headers)

        assert response.status_code == 500

    def test_empty_user_id_header(self, client):
        """Test getting daily summary with empty x-user-id header returns 401."""
        headers = {"x-user-id": ""}
        response = client.get("/daily-summary/2025-09-28", headers=headers)

        assert response.status_code == 401

    def test_user_id_with_whitespace(self, client, registered_user):
        """Test user ID with leading/trailing whitespace."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            headers = {"x-user-id": "  59357664  "}  # With whitespace
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            # The header is looked up as-is (including whitespace); the DB gets the internal ID
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )
            registered_user.assert_awaited_once_with("  59357664  ")

    def test_user_id_case_sensitivity(self, client):
        """Test that x-user-id header is case insensitive (FastAPI behavior)."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            # Test with different case - FastAPI treats headers as case-insensitive
            headers = {"X-User-ID": "59357664"}  # Different case
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            # FastAPI headers are case-insensitive; the DB gets the internal ID
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )

    def test_multiple_user_id_headers(self, client, registered_user):
        """Test behavior with multiple x-user-id headers (HTTP spec behavior)."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            # HTTP headers with same name are concatenated with commas
            # FastAPI will use the first value
            headers = {"x-user-id": "59357664,99999999"}  # Comma-separated values
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            # The full comma-separated value is looked up; the DB gets the internal ID
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )
            registered_user.assert_awaited_once_with("59357664,99999999")

    def test_special_characters_in_user_id(self, client, registered_user):
        """Test user ID with special characters (looked up as is)."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            special_id = "user-!@#$%-id"
            headers = {"x-user-id": special_id}
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )
            registered_user.assert_awaited_once_with(special_id)

    def test_very_long_user_id(self, client, registered_user):
        """Test user ID with very long string."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            long_user_id = "a" * 1000  # Very long user ID
            headers = {"x-user-id": long_user_id}
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            # The header is looked up as-is; the DB gets the internal ID
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )
            registered_user.assert_awaited_once_with(long_user_id)

    def test_numeric_user_id(self, client, registered_user):
        """Test user ID that is purely numeric."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            headers = {"x-user-id": "123456789"}
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            # The header is looked up as-is; the DB gets the internal ID
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )
            registered_user.assert_awaited_once_with("123456789")

    def test_uuid_user_id(self, client, registered_user):
        """Test user ID that is a UUID."""
        with patch(
            "calorie_track_ai_bot.api.v1.daily_summary.db_get_daily_summary"
        ) as mock_db_get_daily_summary:
            mock_db_get_daily_summary.return_value = None

            uuid_user_id = "550e8400-e29b-41d4-a716-446655440000"
            headers = {"x-user-id": uuid_user_id}
            response = client.get("/daily-summary/2025-09-28", headers=headers)

            assert response.status_code == 200
            # The header is looked up as-is; the DB gets the internal ID
            mock_db_get_daily_summary.assert_called_once_with(
                "2025-09-28", INTERNAL_USER_ID, tz="UTC"
            )
            registered_user.assert_awaited_once_with(uuid_user_id)
