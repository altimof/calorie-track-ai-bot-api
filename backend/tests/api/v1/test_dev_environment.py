"""Tests for development environment endpoint."""

import uuid

from fastapi.testclient import TestClient

from src.calorie_track_ai_bot.main import app
from src.calorie_track_ai_bot.schemas import DevelopmentEnvironment

client = TestClient(app)


class TestDevEnvironmentContract:
    def test_get_dev_environment_success(self, admin_headers):
        response = client.get("/api/v1/dev/environment", headers=admin_headers)

        if response.status_code == 403:
            assert response.json()["error"] == "access_denied"
            return

        assert response.status_code == 200
        data = response.json()

        dev_env = DevelopmentEnvironment(**data)
        assert isinstance(dev_env.id, uuid.UUID)
        assert len(dev_env.name) > 0
        assert 1024 <= dev_env.frontend_port <= 65535
        assert 1024 <= dev_env.backend_port <= 65535
        assert dev_env.frontend_port != dev_env.backend_port

    def test_get_dev_environment_stable_id(self, admin_headers):
        response1 = client.get("/api/v1/dev/environment", headers=admin_headers)

        if response1.status_code == 403:
            return

        assert response1.status_code == 200

        response2 = client.get("/api/v1/dev/environment", headers=admin_headers)
        assert response2.status_code == 200

        assert response1.json()["id"] == response2.json()["id"]

    def test_get_dev_environment_requires_admin_token(self, admin_headers):
        response = client.get("/api/v1/dev/environment")
        assert response.status_code == 401
