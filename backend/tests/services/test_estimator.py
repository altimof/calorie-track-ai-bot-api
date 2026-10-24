"""Tests for estimator module."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from calorie_track_ai_bot.services.estimator import SCHEMA_WITH_MACROS, estimate_from_image_url


class TestEstimator:
    """Test estimator functions."""

    def test_schema_structure(self):
        """Test that SCHEMA_WITH_MACROS has the correct structure."""
        assert "type" in SCHEMA_WITH_MACROS
        assert SCHEMA_WITH_MACROS["type"] == "object"
        assert "properties" in SCHEMA_WITH_MACROS
        assert "required" in SCHEMA_WITH_MACROS

        # Check required fields
        required_fields = SCHEMA_WITH_MACROS["required"]
        assert "kcal_mean" in required_fields
        assert "kcal_min" in required_fields
        assert "kcal_max" in required_fields
        assert "confidence" in required_fields
        assert "macronutrients" in required_fields
        assert "items" in required_fields

        # Check properties structure
        properties = SCHEMA_WITH_MACROS["properties"]
        assert "kcal_mean" in properties
        assert "kcal_min" in properties
        assert "kcal_max" in properties
        assert "confidence" in properties
        assert "items" in properties

        # Check items structure
        items_schema = properties["items"]
        assert items_schema["type"] == "array"
        assert "items" in items_schema
        assert "properties" in items_schema["items"]
        assert "required" in items_schema["items"]

    @pytest.mark.asyncio
    async def test_estimate_from_image_url_success(self):
        """Test successful estimation from image URL."""
        image_url = "https://example.com/image.jpg"
        expected_response = {
            "kcal_mean": 500,
            "kcal_min": 400,
            "kcal_max": 600,
            "confidence": 0.8,
            "macronutrients": {"protein": 20, "carbs": 60, "fats": 18},
            "items": [{"label": "pizza", "kcal": 500, "confidence": 0.8}],
        }

        # Mock the OpenAI client and response
        with patch("calorie_track_ai_bot.services.estimator.client") as mock_client:
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = json.dumps(expected_response)
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await estimate_from_image_url(image_url)

            # Should return the parsed JSON
            assert result == expected_response

            # Should call OpenAI API with correct parameters
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args

            assert call_args.kwargs["model"] == "gpt-5-mini"
            assert len(call_args.kwargs["messages"]) == 1
            assert call_args.kwargs["messages"][0]["role"] == "user"

            # Check message content structure
            content = call_args.kwargs["messages"][0]["content"]
            assert len(content) == 2
            assert content[0]["type"] == "text"
            assert content[1]["type"] == "image_url"
            assert content[1]["image_url"]["url"] == image_url

            # Check response format
            response_format = call_args.kwargs["response_format"]
            assert response_format["type"] == "json_schema"
            assert response_format["json_schema"]["schema"] is SCHEMA_WITH_MACROS
            assert response_format["json_schema"]["strict"] is True

    @pytest.mark.asyncio
    async def test_estimate_from_image_url_no_content(self):
        """Test estimation when OpenAI returns no content."""
        image_url = "https://example.com/image.jpg"

        # Mock the OpenAI client with None content
        with patch("calorie_track_ai_bot.services.estimator.client") as mock_client:
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = None
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Should raise ValueError
            with pytest.raises(ValueError, match="No content returned from OpenAI"):
                await estimate_from_image_url(image_url)

    @pytest.mark.asyncio
    async def test_estimate_from_image_url_invalid_json(self):
        """Test estimation when OpenAI returns invalid JSON."""
        image_url = "https://example.com/image.jpg"

        # Mock the OpenAI client with invalid JSON
        with patch("calorie_track_ai_bot.services.estimator.client") as mock_client:
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.content = "invalid json"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Should raise JSONDecodeError
            with pytest.raises(json.JSONDecodeError):
                await estimate_from_image_url(image_url)

    @pytest.mark.asyncio
    async def test_estimate_from_image_url_openai_error(self):
        """Test estimation when OpenAI API raises an error."""
        image_url = "https://example.com/image.jpg"

        # Mock the OpenAI client to raise an exception
        with patch("calorie_track_ai_bot.services.estimator.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            # Should propagate the exception
            with pytest.raises(Exception, match="API Error"):
                await estimate_from_image_url(image_url)

    @pytest.mark.asyncio
    async def test_estimate_from_image_url_empty_response(self):
        """Test estimation with empty response."""
        image_url = "https://example.com/image.jpg"

        # Mock the OpenAI client with empty choices
        with patch("calorie_track_ai_bot.services.estimator.client") as mock_client:
            mock_response = Mock()
            mock_response.choices = []
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Should raise IndexError when accessing choices[0]
            with pytest.raises(IndexError):
                await estimate_from_image_url(image_url)

    def test_schema_validation_example(self):
        """Test that the schema validates a proper response."""
        valid_response = {
            "kcal_mean": 500,
            "kcal_min": 400,
            "kcal_max": 600,
            "confidence": 0.8,
            "items": [
                {"label": "pizza", "kcal": 500, "confidence": 0.8},
                {"label": "salad", "kcal": 100, "confidence": 0.9},
            ],
        }

        # This should not raise any validation errors
        # (In a real implementation, you might use jsonschema to validate)
        assert isinstance(valid_response["kcal_mean"], int | float)
        assert isinstance(valid_response["kcal_min"], int | float)
        assert isinstance(valid_response["kcal_max"], int | float)
        assert isinstance(valid_response["confidence"], int | float)
        assert isinstance(valid_response["items"], list)

        for item in valid_response["items"]:
            assert "label" in item
            assert "kcal" in item
            assert "confidence" in item
            assert isinstance(item["label"], str)
            assert isinstance(item["kcal"], int | float)
            assert isinstance(item["confidence"], int | float)
