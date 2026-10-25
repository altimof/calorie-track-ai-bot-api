import uuid

from fastapi.testclient import TestClient

from src.calorie_track_ai_bot.main import app

client = TestClient(app)

HEADERS = {"x-user-id": "123456789"}


class TestLogsContract:
    def test_post_logs_with_valid_data_returns_200(self):
        log_data = {
            "level": "INFO",
            "message": "User action performed",
            "correlation_id": str(uuid.uuid4()),
            "context": {"action": "photo_upload"},
        }

        response = client.post("/api/v1/logs", json=log_data, headers=HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}

    def test_post_logs_validates_log_level(self):
        invalid_log_data = {
            "level": "INVALID_LEVEL",
            "message": "Test message",
        }

        response = client.post("/api/v1/logs", json=invalid_log_data, headers=HEADERS)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any(
            "Input should be" in str(err) and "INVALID_LEVEL" in str(err) for err in error_detail
        )

    def test_post_logs_validates_required_fields(self):
        incomplete_log_data = {
            "level": "INFO",
        }

        response = client.post("/api/v1/logs", json=incomplete_log_data, headers=HEADERS)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        error_fields = [err.get("loc", [])[-1] if err.get("loc") else "" for err in error_detail]
        assert "message" in error_fields

    def test_post_logs_validates_correlation_id_format(self):
        log_data = {
            "level": "ERROR",
            "message": "Test error message",
            "correlation_id": "invalid-uuid-format",
        }

        response = client.post("/api/v1/logs", json=log_data, headers=HEADERS)

        assert response.status_code == 422

    def test_post_logs_with_context_data(self):
        log_data = {
            "level": "DEBUG",
            "message": "Component rendered",
            "context": {
                "component": "ThemeDetector",
                "theme": "dark",
            },
        }

        response = client.post("/api/v1/logs", json=log_data, headers=HEADERS)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_post_logs_requires_authentication(self):
        log_data = {
            "level": "INFO",
            "message": "Test message",
        }

        response = client.post("/api/v1/logs", json=log_data)

        assert response.status_code == 401

    def test_post_logs_performance_requirement(self):
        import time

        log_data = {
            "level": "INFO",
            "message": "Performance test log",
        }

        start_time = time.perf_counter()
        response = client.post("/api/v1/logs", json=log_data, headers=HEADERS)
        end_time = time.perf_counter()
        response_time_ms = (end_time - start_time) * 1000

        assert response.status_code == 200
        assert response_time_ms < 200, (
            f"Response time was {response_time_ms:.2f}ms, expected < 200ms"
        )


class TestLogsWithoutRegistration:
    def test_post_logs_works_while_database_is_down(self, registered_user):
        """Frontend reports of a DB outage must not be lost to the auth lookup."""
        registered_user.side_effect = RuntimeError("pool exhausted")

        response = client.post(
            "/api/v1/logs", json={"level": "ERROR", "message": "API down"}, headers=HEADERS
        )

        assert response.status_code == 200
        registered_user.assert_not_called()

    def test_post_logs_accepts_unregistered_user(self, registered_user):
        registered_user.return_value = None

        response = client.post(
            "/api/v1/logs", json={"level": "INFO", "message": "hello"}, headers=HEADERS
        )

        assert response.status_code == 200
