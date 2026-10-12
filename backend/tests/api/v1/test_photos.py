"""Tests for photos API endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from calorie_track_ai_bot.api.v1.deps import get_authenticated_user_id
from calorie_track_ai_bot.api.v1.photos import router

USER_ID = "1d882190-ac3f-4a06-8a44-20e46bafb9a5"


class TestPhotosEndpoints:
    """Test photo-related endpoints."""

    @pytest.fixture
    def client(self):
        """Test client whose requests come from USER_ID."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_authenticated_user_id] = lambda: USER_ID
        return TestClient(app)

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    @patch("calorie_track_ai_bot.api.v1.photos.db_create_photo")
    def test_create_photo_success(self, mock_db_create, mock_presign, client):
        """Test successful photo creation."""
        # Mock the async functions
        mock_presign.return_value = ("photos/test123.jpg", "https://presigned-url.example.com")
        mock_db_create.return_value = "photo-uuid-123"

        payload = {"content_type": "image/jpeg"}

        response = client.post("/photos", json=payload)

        assert response.status_code == 200
        mock_db_create.assert_awaited_once_with(tigris_key="photos/test123.jpg", user_id=USER_ID)
        data = response.json()

        # Check response structure
        assert "photo_id" in data
        assert "upload_url" in data

        # Check values
        assert data["photo_id"] == "photo-uuid-123"
        assert data["upload_url"] == "https://presigned-url.example.com"

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    @patch("calorie_track_ai_bot.api.v1.photos.db_create_photo")
    def test_create_photo_different_content_types(self, mock_db_create, mock_presign, client):
        """Test photo creation with different content types."""
        mock_presign.return_value = ("photos/test456.jpg", "https://presigned-url.example.com")
        mock_db_create.return_value = "photo-uuid-456"

        test_cases = ["image/png", "image/webp", "image/gif", "application/octet-stream"]

        for content_type in test_cases:
            payload = {"content_type": content_type}
            response = client.post("/photos", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert "photo_id" in data
            assert "upload_url" in data

    def test_create_photo_missing_content_type(self, client):
        """Test photo creation with missing content_type."""
        payload = {}

        response = client.post("/photos", json=payload)

        # Should return validation error
        assert response.status_code == 422

    def test_create_photo_invalid_content_type(self, client):
        """Test photo creation with invalid content_type."""
        payload = {"content_type": 123}  # Should be string

        response = client.post("/photos", json=payload)

        # Should return validation error
        assert response.status_code == 422

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    @patch("calorie_track_ai_bot.api.v1.photos.db_create_photo")
    def test_create_photo_empty_content_type(self, mock_db_create, mock_presign, client):
        """Test photo creation with empty content_type."""
        mock_presign.return_value = ("photos/test.jpg", "https://presigned-url.example.com")
        mock_db_create.return_value = "photo-uuid-empty"

        payload = {"content_type": ""}

        response = client.post("/photos", json=payload)

        # Should still work (empty string is valid)
        assert response.status_code == 200

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    @patch("calorie_track_ai_bot.api.v1.photos.db_create_photo")
    def test_create_photo_presign_error(self, mock_db_create, mock_presign, client):
        """Test photo creation when presign fails."""
        mock_presign.side_effect = Exception("S3 Error")
        mock_db_create.return_value = "photo-uuid-error"

        payload = {"content_type": "image/jpeg"}

        # Should propagate the error
        response = client.post("/photos", json=payload)
        assert response.status_code == 500

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    @patch("calorie_track_ai_bot.api.v1.photos.db_create_photo")
    def test_create_photo_db_error(self, mock_db_create, mock_presign, client):
        """Test photo creation when database save fails."""
        mock_presign.return_value = ("photos/test789.jpg", "https://presigned-url.example.com")
        mock_db_create.side_effect = Exception("Database Error")

        payload = {"content_type": "image/jpeg"}

        # Should propagate the error
        response = client.post("/photos", json=payload)
        assert response.status_code == 500

    def test_create_photo_methods(self, client):
        """Test that create photo only accepts POST requests."""
        get_response = client.get("/photos")
        assert get_response.status_code == 405  # Method Not Allowed

        put_response = client.put("/photos")
        assert put_response.status_code == 405

        delete_response = client.delete("/photos")
        assert delete_response.status_code == 405

    def test_create_photo_content_type(self, client):
        """Test that create photo returns JSON content type."""
        with (
            patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put") as mock_presign,
            patch("calorie_track_ai_bot.api.v1.photos.db_create_photo") as mock_db_create,
        ):
            mock_presign.return_value = ("photos/test.jpg", "https://url.com")
            mock_db_create.return_value = "photo-uuid-content"

            payload = {"content_type": "image/jpeg"}
            response = client.post("/photos", json=payload)

            assert response.headers["content-type"] == "application/json"

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    @patch("calorie_track_ai_bot.api.v1.photos.db_create_photo")
    def test_create_photo_response_structure(self, mock_db_create, mock_presign, client):
        """Test that create photo returns consistent response structure."""
        mock_presign.return_value = ("photos/test.jpg", "https://presigned-url.example.com")
        mock_db_create.return_value = "photo-uuid-structure"

        payload = {"content_type": "image/jpeg"}
        response = client.post("/photos", json=payload)

        data = response.json()

        # Should be valid JSON
        assert isinstance(data, dict)

        # Should have required fields
        assert "photo_id" in data
        assert "upload_url" in data

        # Values should be strings
        assert isinstance(data["photo_id"], str)
        assert isinstance(data["upload_url"], str)

        # photo_id should be the same as the key from presign
        assert data["photo_id"] == "photo-uuid-structure"


class TestPhotosRequireRegisteredUser:
    """Without a registered user, no upload URL is handed out."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    def test_create_photo_without_auth_returns_401(self, mock_presign, client):
        response = client.post("/photos", json={"content_type": "image/jpeg"})
        assert response.status_code == 401
        mock_presign.assert_not_called()

    @patch("calorie_track_ai_bot.api.v1.photos.tigris_presign_put")
    def test_create_photo_unregistered_user_returns_403(
        self, mock_presign, client, registered_user
    ):
        registered_user.return_value = None
        response = client.post(
            "/photos", json={"content_type": "image/jpeg"}, headers={"x-user-id": "59357664"}
        )
        assert response.status_code == 403
        mock_presign.assert_not_called()
