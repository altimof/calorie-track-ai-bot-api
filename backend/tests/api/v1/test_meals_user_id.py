"""Tests for meals API user ID detection and authentication."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from calorie_track_ai_bot.schemas import Macronutrients, MealWithPhotos


class TestMealsUserIdDetection:
    """Test user ID header handling for meals endpoint."""

    @pytest.fixture
    def mock_meals_data(self):
        """Sample meals data for testing."""
        return [
            MealWithPhotos(
                id="550e8400-e29b-41d4-a716-446655440001",
                userId="550e8400-e29b-41d4-a716-446655440000",
                calories=500,
                macronutrients=Macronutrients(protein=20, carbs=60, fats=15),
                photos=[],
                createdAt=datetime(2025, 9, 28, 8, 0, 0, tzinfo=UTC),
            ),
            MealWithPhotos(
                id="550e8400-e29b-41d4-a716-446655440002",
                userId="550e8400-e29b-41d4-a716-446655440000",
                calories=700,
                macronutrients=Macronutrients(protein=30, carbs=80, fats=25),
                photos=[],
                createdAt=datetime(2025, 9, 28, 13, 0, 0, tzinfo=UTC),
            ),
        ]

    def test_get_meals_without_user_id_header(self, api_client):
        """Test getting meals without x-user-id header returns 401."""
        response = api_client.get("/api/v1/meals")

        assert response.status_code == 401
        assert "Missing Telegram initData" in response.json()["detail"]

    def test_empty_user_id_header(self, api_client):
        """Test getting meals with empty x-user-id header returns 401."""
        headers = {"x-user-id": ""}
        response = api_client.get("/api/v1/meals", headers=headers)

        assert response.status_code == 401

    def test_get_meals_database_error(self, api_client, authenticated_headers):
        """Test getting meals when database error occurs returns 500."""
        with patch(
            "calorie_track_ai_bot.api.v1.meals.db_get_meals_with_photos"
        ) as mock_db_get_meals:
            mock_db_get_meals.side_effect = Exception("Database connection failed")

            response = api_client.get("/api/v1/meals", headers=authenticated_headers)

            assert response.status_code == 500

    def test_get_meals_with_telegram_user_id(
        self, api_client, authenticated_headers, mock_meals_data
    ):
        """Test happy path: getting meals with valid telegram user ID."""
        with (
            patch(
                "calorie_track_ai_bot.api.v1.meals.db_get_meals_with_photos"
            ) as mock_db_get_meals,
            patch("calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve_user_id,
        ):
            mock_resolve_user_id.return_value = "550e8400-e29b-41d4-a716-446655440000"
            mock_db_get_meals.return_value = mock_meals_data

            response = api_client.get("/api/v1/meals", headers=authenticated_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data["meals"]) == 2
            assert data["meals"][0]["id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert data["meals"][1]["id"] == "550e8400-e29b-41d4-a716-446655440002"

    @pytest.mark.parametrize(
        ("header_name", "header_value"),
        [
            ("x-user-id", "  59357664  "),  # whitespace
            ("x-user-id", "123456789"),  # numeric
            ("X-User-Id", "59357664"),  # case-insensitive header name
        ],
        ids=["whitespace", "numeric", "case-insensitive-header"],
    )
    def test_user_id_edge_cases(self, api_client, header_name, header_value):
        """Test that resolve_user_id is called for various user ID formats."""
        headers = {header_name: header_value}
        with (
            patch(
                "calorie_track_ai_bot.api.v1.meals.db_get_meals_with_photos"
            ) as mock_db_get_meals,
            patch("calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve_user_id,
        ):
            mock_resolve_user_id.return_value = "550e8400-e29b-41d4-a716-446655440000"
            mock_db_get_meals.return_value = []

            response = api_client.get("/api/v1/meals", headers=headers)

            assert response.status_code == 200
