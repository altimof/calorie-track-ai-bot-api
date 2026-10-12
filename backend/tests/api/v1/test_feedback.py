"""Tests for Feedback API endpoints.

Feature: 005-mini-app-improvements
Tests cover feedback submission, validation, and error handling.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from src.calorie_track_ai_bot.main import app
from src.calorie_track_ai_bot.schemas import (
    FeedbackMessageType,
    FeedbackStatus,
    FeedbackSubmission,
    FeedbackSubmissionResponse,
)

client = TestClient(app)


class TestFeedbackSubmissionContract:
    """Test feedback submission API contracts."""

    def test_submit_feedback_with_valid_data_returns_201(self):
        """Test that POST /api/v1/feedback returns 201 with valid feedback data."""
        with (
            patch(
                "src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service"
            ) as mock_get_service,
            patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
        ):
            # Setup mocks
            mock_user_id = str(uuid.uuid4())
            mock_resolve.return_value = mock_user_id

            feedback_id = uuid.uuid4()
            created_at = datetime.now(UTC)
            mock_service = Mock()
            mock_service.submit_feedback = AsyncMock(
                return_value=FeedbackSubmissionResponse(
                    id=feedback_id,
                    status=FeedbackStatus.new,
                    created_at=created_at,
                    message="Thank you! We received your feedback.",
                )
            )
            mock_get_service.return_value = mock_service

            # Valid feedback data
            feedback_data = {
                "message_type": "feedback",
                "message_content": "Great app! Love the calorie tracking feature.",
                "user_context": {
                    "page": "/feedback",
                    "user_agent": "Mozilla/5.0",
                    "app_version": "0.1.0",
                    "language": "en",
                },
            }

            # Make request with required headers
            response = client.post(
                "/api/v1/feedback",
                json=feedback_data,
                headers={"x-user-id": "123456789"},
            )

            assert response.status_code == 201
            data = response.json()

            # Validate response against FeedbackSubmissionResponse schema
            feedback_response = FeedbackSubmissionResponse(**data)
            assert str(feedback_response.id) == str(feedback_id)
            assert feedback_response.status == FeedbackStatus.new
            assert feedback_response.message == "Thank you! We received your feedback."
            assert isinstance(feedback_response.created_at, datetime)

    def test_submit_feedback_without_auth_returns_401(self):
        """Test that feedback submission without x-user-id header returns 401."""
        feedback_data = {
            "message_type": "feedback",
            "message_content": "Test feedback",
        }

        # Request without x-user-id header
        response = client.post("/api/v1/feedback", json=feedback_data)

        assert response.status_code == 401
        assert "initdata" in response.json()["detail"].lower()

    def test_submit_feedback_validates_message_type(self):
        """Test that invalid message_type is rejected."""
        invalid_feedback_data = {
            "message_type": "other",  # Invalid type (not in enum)
            "message_content": "Test feedback",
        }

        response = client.post(
            "/api/v1/feedback",
            json=invalid_feedback_data,
            headers={"x-user-id": "123456789"},
        )

        # Should return 422 for invalid enum value (Pydantic validation error)
        assert response.status_code == 422
        assert "message_type" in str(response.json()).lower()

    def test_submit_feedback_validates_message_types(self):
        """Test that all valid message types are accepted."""
        valid_types = ["feedback", "bug", "question", "support"]

        for message_type in valid_types:
            with (
                patch(
                    "src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service"
                ) as mock_get_service,
                patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
            ):
                mock_resolve.return_value = str(uuid.uuid4())
                mock_service = Mock()
                mock_service.submit_feedback = AsyncMock(
                    return_value=FeedbackSubmissionResponse(
                        id=uuid.uuid4(),
                        status=FeedbackStatus.new,
                        created_at=datetime.now(UTC),
                        message="Thank you!",
                    )
                )
                mock_get_service.return_value = mock_service

                feedback_data = {
                    "message_type": message_type,
                    "message_content": f"Test {message_type} message",
                }

                response = client.post(
                    "/api/v1/feedback",
                    json=feedback_data,
                    headers={"x-user-id": "123456789"},
                )

                assert response.status_code == 201, f"Failed for type: {message_type}"

    def test_submit_feedback_validates_empty_message(self):
        """Test that empty message_content is rejected."""
        invalid_feedback_data = {
            "message_type": "feedback",
            "message_content": "",  # Empty message
        }

        response = client.post(
            "/api/v1/feedback",
            json=invalid_feedback_data,
            headers={"x-user-id": "123456789"},
        )

        assert response.status_code == 422
        assert "message_content" in str(response.json()).lower()

    def test_submit_feedback_validates_message_length(self):
        """Test that message_content length validation works."""
        # Message exceeding 5000 characters
        long_message = "x" * 5001

        invalid_feedback_data = {
            "message_type": "feedback",
            "message_content": long_message,
        }

        response = client.post(
            "/api/v1/feedback",
            json=invalid_feedback_data,
            headers={"x-user-id": "123456789"},
        )

        assert response.status_code == 422
        assert "message_content" in str(response.json()).lower()

    def test_submit_feedback_accepts_max_length_message(self):
        """Test that message at maximum length (5000 chars) is accepted."""
        max_length_message = "x" * 5000

        with (
            patch(
                "src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service"
            ) as mock_get_service,
            patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
        ):
            mock_resolve.return_value = str(uuid.uuid4())
            mock_service = Mock()
            mock_service.submit_feedback = AsyncMock(
                return_value=FeedbackSubmissionResponse(
                    id=uuid.uuid4(),
                    status=FeedbackStatus.new,
                    created_at=datetime.now(UTC),
                    message="Thank you!",
                )
            )
            mock_get_service.return_value = mock_service

            feedback_data = {
                "message_type": "feedback",
                "message_content": max_length_message,
            }

            response = client.post(
                "/api/v1/feedback",
                json=feedback_data,
                headers={"x-user-id": "123456789"},
            )

            assert response.status_code == 201

    def test_submit_feedback_with_user_context(self):
        """Test that user_context is optional and properly handled."""
        with (
            patch(
                "src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service"
            ) as mock_get_service,
            patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
        ):
            mock_resolve.return_value = str(uuid.uuid4())
            mock_service = Mock()
            mock_service.submit_feedback = AsyncMock(
                return_value=FeedbackSubmissionResponse(
                    id=uuid.uuid4(),
                    status=FeedbackStatus.new,
                    created_at=datetime.now(UTC),
                    message="Thank you!",
                )
            )
            mock_get_service.return_value = mock_service

            # Test without user_context
            feedback_data = {
                "message_type": "feedback",
                "message_content": "Test message",
            }

            response = client.post(
                "/api/v1/feedback",
                json=feedback_data,
                headers={"x-user-id": "123456789"},
            )

            assert response.status_code == 201

    def test_submit_feedback_with_unregistered_user_returns_403(self):
        """Test that feedback submission from an unregistered user returns 403."""
        with patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve:
            mock_resolve.return_value = None  # User not found

            feedback_data = {
                "message_type": "feedback",
                "message_content": "Test message",
            }

            response = client.post(
                "/api/v1/feedback",
                json=feedback_data,
                headers={"x-user-id": "invalid_user"},
            )

            assert response.status_code == 403
            assert response.json()["detail"] == "User not registered"


class TestFeedbackRetrievalContract:
    """Test feedback retrieval API contracts."""

    def test_get_feedback_by_id_returns_200(self):
        """Test that GET /api/v1/feedback/{id} returns 200 with valid feedback."""
        with (
            patch(
                "src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service"
            ) as mock_get_service,
            patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
        ):
            # Setup mocks
            mock_user_id = str(uuid.uuid4())
            mock_resolve.return_value = mock_user_id

            feedback_id = uuid.uuid4()
            created_at = datetime.now(UTC)
            mock_service = Mock()
            mock_service.get_feedback = AsyncMock(
                return_value=FeedbackSubmission(
                    id=feedback_id,
                    user_id=mock_user_id,
                    message_type=FeedbackMessageType.feedback,
                    message_content="Test feedback",
                    user_context={"page": "/feedback"},
                    status=FeedbackStatus.new,
                    admin_notes=None,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            mock_get_service.return_value = mock_service

            response = client.get(
                f"/api/v1/feedback/{feedback_id}", headers={"x-user-id": "123456789"}
            )

            assert response.status_code == 200
            data = response.json()

            # Validate response
            feedback = FeedbackSubmission(**data)
            assert str(feedback.id) == str(feedback_id)
            assert feedback.message_content == "Test feedback"
            assert feedback.status == FeedbackStatus.new

    def test_get_nonexistent_feedback_returns_404(self):
        """Test that GET returns 404 for non-existent feedback."""
        with (
            patch(
                "src.calorie_track_ai_bot.api.v1.feedback.get_feedback_service"
            ) as mock_get_service,
            patch("src.calorie_track_ai_bot.api.v1.deps.resolve_user_id") as mock_resolve,
        ):
            mock_resolve.return_value = str(uuid.uuid4())
            mock_service = Mock()
            mock_service.get_feedback = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            feedback_id = uuid.uuid4()
            response = client.get(
                f"/api/v1/feedback/{feedback_id}", headers={"x-user-id": "123456789"}
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_feedback_without_auth_returns_401(self):
        """Test that GET without x-user-id header returns 401."""
        feedback_id = uuid.uuid4()
        response = client.get(f"/api/v1/feedback/{feedback_id}")

        assert response.status_code == 401
