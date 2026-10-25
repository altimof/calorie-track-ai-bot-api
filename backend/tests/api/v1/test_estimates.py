"""Tests for estimates API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from calorie_track_ai_bot.api.v1.deps import get_authenticated_user_id
from calorie_track_ai_bot.api.v1.estimates import router

USER_ID = "1d882190-ac3f-4a06-8a44-20e46bafb9a5"
PHOTO_ID = "6f1c2a3e-8b4d-4c5e-9f60-7a8b9c0d1e2f"
ESTIMATE_ID = "7dd63665-3a87-4e14-8ec6-dcfe779cba00"


def make_estimate(estimate_id: str = ESTIMATE_ID) -> dict:
    return {
        "id": estimate_id,
        "photo_id": PHOTO_ID,
        "kcal_mean": 500,
        "kcal_min": 400,
        "kcal_max": 600,
        "confidence": 0.8,
        "breakdown": [{"label": "pizza", "kcal": 500, "confidence": 0.8}],
        "status": "done",
    }


class TestEstimatesEndpoints:
    """Test estimate-related endpoints for a registered user."""

    @pytest.fixture
    def client(self):
        """Test client whose requests come from USER_ID."""
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_authenticated_user_id] = lambda: USER_ID
        return TestClient(app)

    @pytest.fixture
    def owned_photo(self):
        """The requested photo belongs to the requesting user."""
        with patch(
            "calorie_track_ai_bot.api.v1.estimates.db_get_user_photo",
            AsyncMock(return_value={"id": PHOTO_ID, "user_id": USER_ID}),
        ) as mock_get_photo:
            yield mock_get_photo

    @patch("calorie_track_ai_bot.api.v1.estimates.enqueue_estimate_job")
    def test_estimate_photo_success(self, mock_enqueue, client, owned_photo):
        """Test successful photo estimation request."""
        mock_enqueue.return_value = "job123"

        response = client.post(f"/photos/{PHOTO_ID}/estimate")

        assert response.status_code == 200
        assert response.json() == {"estimate_id": "job123", "status": "queued"}
        owned_photo.assert_awaited_once_with(PHOTO_ID, USER_ID)
        mock_enqueue.assert_awaited_once_with(PHOTO_ID, source="api")

    @patch("calorie_track_ai_bot.api.v1.estimates.enqueue_estimate_job")
    def test_estimate_other_users_photo_returns_404(self, mock_enqueue, client, owned_photo):
        """A photo that isn't the user's is reported as missing, and nothing is queued."""
        owned_photo.return_value = None

        response = client.post(f"/photos/{PHOTO_ID}/estimate")

        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
        mock_enqueue.assert_not_called()

    @pytest.mark.parametrize("photo_id", ["photo123", "test-photo-789"])
    @patch("calorie_track_ai_bot.api.v1.estimates.enqueue_estimate_job")
    def test_estimate_malformed_photo_id_returns_404(
        self, mock_enqueue, client, owned_photo, photo_id
    ):
        """Non-UUID IDs are rejected without a database lookup."""
        response = client.post(f"/photos/{photo_id}/estimate")

        assert response.status_code == 404
        owned_photo.assert_not_called()
        mock_enqueue.assert_not_called()

    @patch("calorie_track_ai_bot.api.v1.estimates.enqueue_estimate_job")
    def test_estimate_photo_queue_error(self, mock_enqueue, client, owned_photo):
        """Test photo estimation when queue operation fails."""
        mock_enqueue.side_effect = Exception("Queue Error")

        response = client.post(f"/photos/{PHOTO_ID}/estimate")

        assert response.status_code == 500

    def test_estimate_photo_methods(self, client):
        """Test that estimate photo only accepts POST requests."""
        assert client.get(f"/photos/{PHOTO_ID}/estimate").status_code == 405
        assert client.put(f"/photos/{PHOTO_ID}/estimate").status_code == 405
        assert client.delete(f"/photos/{PHOTO_ID}/estimate").status_code == 405

    @patch("calorie_track_ai_bot.api.v1.estimates.db_get_user_estimate")
    def test_get_estimate_success(self, mock_db_get, client):
        """Test successful estimate retrieval."""
        mock_db_get.return_value = make_estimate()

        response = client.get(f"/estimates/{ESTIMATE_ID}")

        assert response.status_code == 200
        assert response.json() == make_estimate()
        mock_db_get.assert_awaited_once_with(ESTIMATE_ID, USER_ID)

    @patch("calorie_track_ai_bot.api.v1.estimates.db_get_user_estimate")
    def test_get_estimate_not_found_or_not_owned(self, mock_db_get, client):
        """Missing estimates and other users' estimates both return 404."""
        mock_db_get.return_value = None

        response = client.get(f"/estimates/{ESTIMATE_ID}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    @patch("calorie_track_ai_bot.api.v1.estimates.db_get_user_estimate")
    def test_get_estimate_malformed_id_returns_404(self, mock_db_get, client):
        """Non-UUID IDs are rejected without a database lookup."""
        response = client.get("/estimates/nonexistent")

        assert response.status_code == 404
        mock_db_get.assert_not_called()

    @patch("calorie_track_ai_bot.api.v1.estimates.db_get_user_estimate")
    def test_get_estimate_urn_id_is_canonicalized(self, mock_db_get, client):
        """Forms uuid.UUID accepts but Postgres rejects reach SQL in canonical form."""
        mock_db_get.return_value = None

        response = client.get(f"/estimates/urn:uuid:{ESTIMATE_ID}")

        assert response.status_code == 404
        mock_db_get.assert_awaited_once_with(ESTIMATE_ID, USER_ID)

    @patch("calorie_track_ai_bot.api.v1.estimates.enqueue_estimate_job")
    def test_estimate_photo_urn_id_is_canonicalized(self, mock_enqueue, client, owned_photo):
        """The photo lookup and the job get the canonical photo ID."""
        mock_enqueue.return_value = "job123"

        response = client.post(f"/photos/urn:uuid:{PHOTO_ID}/estimate")

        assert response.status_code == 200
        owned_photo.assert_awaited_once_with(PHOTO_ID, USER_ID)
        mock_enqueue.assert_awaited_once_with(PHOTO_ID, source="api")

    @patch("calorie_track_ai_bot.api.v1.estimates.db_get_user_estimate")
    def test_get_estimate_db_error(self, mock_db_get, client):
        """Test estimate retrieval when database operation fails."""
        mock_db_get.side_effect = Exception("Database Error")

        response = client.get(f"/estimates/{ESTIMATE_ID}")

        assert response.status_code == 500

    def test_get_estimate_methods(self, client):
        """Test that get estimate only accepts GET requests."""
        assert client.post(f"/estimates/{ESTIMATE_ID}").status_code == 405
        assert client.put(f"/estimates/{ESTIMATE_ID}").status_code == 405
        assert client.delete(f"/estimates/{ESTIMATE_ID}").status_code == 405

    def test_estimate_endpoints_content_type(self, client, owned_photo):
        """Test that estimate endpoints return JSON content type."""
        with (
            patch("calorie_track_ai_bot.api.v1.estimates.enqueue_estimate_job") as mock_enqueue,
            patch("calorie_track_ai_bot.api.v1.estimates.db_get_user_estimate") as mock_db_get,
        ):
            mock_enqueue.return_value = "job123"
            mock_db_get.return_value = make_estimate()

            post_response = client.post(f"/photos/{PHOTO_ID}/estimate")
            assert post_response.headers["content-type"] == "application/json"

            get_response = client.get(f"/estimates/{ESTIMATE_ID}")
            assert get_response.headers["content-type"] == "application/json"


class TestEstimatesRequireRegisteredUser:
    """Without a registered user, the endpoints refuse the request."""

    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_estimate_photo_without_auth_returns_401(self, client):
        assert client.post(f"/photos/{PHOTO_ID}/estimate").status_code == 401

    def test_get_estimate_without_auth_returns_401(self, client):
        assert client.get(f"/estimates/{ESTIMATE_ID}").status_code == 401

    def test_unregistered_user_returns_403(self, client, registered_user):
        registered_user.return_value = None
        response = client.get(f"/estimates/{ESTIMATE_ID}", headers={"x-user-id": "59357664"})
        assert response.status_code == 403
