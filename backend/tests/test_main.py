"""Tests for main application."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from calorie_track_ai_bot.main import app


class TestMainApplication:
    """Test main FastAPI application."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_app_title(self, client):
        """Test that app has correct title."""
        # Get OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert schema["info"]["title"] == "Calories Count API"
        assert schema["info"]["version"] == "0.1.0"

    def test_health_endpoints_available(self, client):
        """Test that health endpoints are available."""
        # Test live endpoint
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        # Test ready endpoint
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        # Test healthz endpoint (for Fly.io)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_photos_endpoints_available(self, client):
        """Test that photos endpoints are available."""
        # The endpoint exists and requires authentication
        response = client.post("/api/v1/photos")
        assert response.status_code == 401

    def test_estimates_endpoints_available(self, client):
        """Test that estimates endpoints are available."""
        headers = {"x-user-id": "123456789"}

        # The routes exist: an unknown ID gets the endpoints' own 404, not the router's
        response = client.post("/api/v1/photos/test123/estimate", headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

        response = client.get("/api/v1/estimates/test123", headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    def test_meals_endpoints_available(self, client):
        """Test that meals endpoints are available."""
        # Test that endpoint exists (will fail validation but endpoint exists)
        response = client.post("/api/v1/meals")
        assert response.status_code == 422  # Validation error, but endpoint exists

    def test_cors_headers(self, client):
        """Test that CORS headers are properly set."""
        # Make a regular request with Origin header to test CORS
        response = client.get("/health/live", headers={"Origin": "http://localhost:5173"})

        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_cors_preflight_request(self, client):
        """Test CORS preflight request."""
        response = client.options(
            "/api/v1/photos",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Should return 200 for preflight
        assert response.status_code == 200

        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    def test_openapi_docs_available(self, client):
        """Test that OpenAPI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200

        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json_available(self, client):
        """Test that OpenAPI JSON is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_router_prefixes(self, client):
        """Test that routers are mounted with correct prefixes."""
        # Health endpoints should be under /health
        response = client.get("/health/live")
        assert response.status_code == 200

        # API endpoints should be under /api/v1
        response = client.get("/api/v1/config/theme", headers={"x-user-id": "123456789"})
        assert response.status_code == 200

    def test_404_for_nonexistent_endpoints(self, client):
        """Test that nonexistent endpoints return 404."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

        response = client.post("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_app_startup(self, client):
        """Test that app starts up correctly."""
        # Just making sure the app can be instantiated and basic endpoints work
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_all_routers_included(self, client):
        """Test that all expected routers are included."""
        # Get OpenAPI schema to check paths
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema["paths"]

        # Check that all expected paths exist
        expected_paths = [
            "/health/live",
            "/health/ready",
            "/healthz",
            "/api/v1/photos",
            "/api/v1/photos/{photo_id}/estimate",
            "/api/v1/estimates/{estimate_id}",
            "/api/v1/meals",
        ]

        for path in expected_paths:
            assert path in paths, f"Path {path} not found in OpenAPI schema"


class TestHealthConnectivity:
    """Contract tests for the /health/connectivity endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_connectivity_returns_valid_schema(self, client):
        """Test that GET /health/connectivity returns 200 with valid response schema."""
        response = client.get("/health/connectivity")

        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "response_time_ms" in data
        assert "timestamp" in data
        assert "correlation_id" in data

        # Validate field types and constraints
        assert data["status"] in ["connected", "disconnected", "error"]
        assert isinstance(data["response_time_ms"], int | float)
        assert data["response_time_ms"] >= 0
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["correlation_id"], str)

        # Validate correlation_id is a valid UUID
        UUID(data["correlation_id"])

        # Validate timestamp format (ISO 8601)
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_connectivity_idempotency(self, client):
        """Test that multiple calls return unique correlation IDs."""
        responses = [client.get("/health/connectivity") for _ in range(3)]

        for response in responses:
            assert response.status_code == 200

        correlation_ids = [response.json()["correlation_id"] for response in responses]
        assert len(set(correlation_ids)) == 3
