"""Contract tests for POST /api/v1/photos with multi-photo support."""

from unittest.mock import patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_create_single_photo(api_client, authenticated_headers, mock_db_pool):
    """Test POST /api/v1/photos with single photo returns upload URL."""
    payload = {"photos": [{"content_type": "image/jpeg"}]}

    photo_id = str(uuid4())

    # Mock the storage and database functions
    with (
        patch(
            "calorie_track_ai_bot.api.v1.photos.tigris_presign_put",
            return_value=("test/photo.jpg", "https://test.com/upload"),
        ),
        patch("calorie_track_ai_bot.api.v1.photos.db_create_photo", return_value=photo_id),
    ):
        response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    assert response.status_code == 200
    data = response.json()

    assert "photos" in data
    assert len(data["photos"]) == 1

    photo = data["photos"][0]
    assert "id" in photo
    assert "upload_url" in photo
    assert "file_key" in photo
    assert isinstance(photo["upload_url"], str)


@pytest.mark.asyncio
async def test_create_multiple_photos(api_client, authenticated_headers, mock_db_pool):
    """Test POST /api/v1/photos with multiple photos (up to 5)."""
    payload = {"photos": [{"content_type": "image/jpeg"} for i in range(3)]}

    # Mock the storage and database functions
    with (
        patch(
            "calorie_track_ai_bot.api.v1.photos.tigris_presign_put",
            return_value=("test/photo.jpg", "https://test.com/upload"),
        ),
        patch(
            "calorie_track_ai_bot.api.v1.photos.db_create_photo",
            side_effect=[str(uuid4()) for _ in range(3)],
        ),
    ):
        response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    assert response.status_code == 200
    data = response.json()

    assert len(data["photos"]) == 3

    for _i, photo in enumerate(data["photos"]):
        assert "id" in photo
        assert "upload_url" in photo
        assert "file_key" in photo
        assert isinstance(photo["upload_url"], str)


@pytest.mark.asyncio
async def test_create_max_photos(api_client, authenticated_headers, mock_db_pool):
    """Test POST /api/v1/photos with maximum 5 photos."""
    payload = {"photos": [{"content_type": "image/jpeg"} for i in range(5)]}

    # Mock the storage and database functions
    with (
        patch(
            "calorie_track_ai_bot.api.v1.photos.tigris_presign_put",
            return_value=("test/photo.jpg", "https://test.com/upload"),
        ),
        patch(
            "calorie_track_ai_bot.api.v1.photos.db_create_photo",
            side_effect=[str(uuid4()) for _ in range(5)],
        ),
    ):
        response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    assert response.status_code == 200
    data = response.json()

    assert len(data["photos"]) == 5


@pytest.mark.asyncio
async def test_create_too_many_photos(api_client, authenticated_headers):
    """Test POST /api/v1/photos with more than 5 photos returns 422."""
    payload = {"photos": [{"content_type": "image/jpeg"} for i in range(6)]}

    response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_empty_photos_list(api_client, authenticated_headers):
    """Test POST /api/v1/photos with empty photos list returns 422."""
    payload = {"photos": []}

    response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_photos_without_auth(api_client, mock_db_pool):
    """Test POST /api/v1/photos without authentication is rejected before any upload URL."""
    payload = {"photos": [{"content_type": "image/jpeg"}]}

    # Mock the storage and database functions
    with (
        patch(
            "calorie_track_ai_bot.api.v1.photos.tigris_presign_put",
            return_value=("test/photo.jpg", "https://test.com/upload"),
        ),
        patch("calorie_track_ai_bot.api.v1.photos.db_create_photo", return_value=str(uuid4())),
    ):
        response = api_client.post("/api/v1/photos", json=payload)

    # Upload URLs are only handed out to registered users
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_photos_invalid_content_type(api_client, authenticated_headers, mock_db_pool):
    """Test POST /api/v1/photos with invalid content type."""
    payload = {"photos": [{"content_type": "invalid/type"}]}

    # Mock the storage and database functions
    with (
        patch(
            "calorie_track_ai_bot.api.v1.photos.tigris_presign_put",
            return_value=("test/photo.jpg", "https://test.com/upload"),
        ),
        patch("calorie_track_ai_bot.api.v1.photos.db_create_photo", return_value=str(uuid4())),
    ):
        response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    # Should still succeed as content_type validation happens at upload time
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_photos_mixed_content_types(api_client, authenticated_headers, mock_db_pool):
    """Test POST /api/v1/photos with mixed content types."""
    payload = {
        "photos": [
            {"content_type": "image/jpeg"},
            {"content_type": "image/png"},
            {"content_type": "image/webp"},
        ]
    }

    # Mock the storage and database functions
    with (
        patch(
            "calorie_track_ai_bot.api.v1.photos.tigris_presign_put",
            return_value=("test/photo.jpg", "https://test.com/upload"),
        ),
        patch(
            "calorie_track_ai_bot.api.v1.photos.db_create_photo",
            side_effect=[str(uuid4()) for _ in range(3)],
        ),
    ):
        response = api_client.post("/api/v1/photos", json=payload, headers=authenticated_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["photos"]) == 3
