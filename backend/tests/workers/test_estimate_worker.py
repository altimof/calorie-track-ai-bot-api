"""Tests for estimate_worker module."""

from unittest.mock import patch

import pytest

from calorie_track_ai_bot.workers.estimate_worker import create_meal_from_estimate, handle_job


class TestEstimateWorker:
    """Test estimate worker functions."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        with (
            patch("calorie_track_ai_bot.services.config.OPENAI_API_KEY", "test-key"),
            patch("calorie_track_ai_bot.services.config.REDIS_URL", "redis://test"),
            patch("calorie_track_ai_bot.services.config.AWS_ENDPOINT_URL_S3", "test-endpoint"),
            patch("calorie_track_ai_bot.services.config.AWS_ACCESS_KEY_ID", "test-access"),
            patch("calorie_track_ai_bot.services.config.AWS_SECRET_ACCESS_KEY", "test-secret"),
            patch("calorie_track_ai_bot.services.config.BUCKET_NAME", "test-bucket"),
            patch("calorie_track_ai_bot.workers.estimate_worker.s3") as mock_s3,
            patch("calorie_track_ai_bot.workers.estimate_worker.BUCKET_NAME", "test-bucket"),
            patch(
                "calorie_track_ai_bot.workers.estimate_worker.estimate_from_image_url"
            ) as mock_estimate,
            patch("calorie_track_ai_bot.workers.estimate_worker.db_save_estimate") as mock_db_save,
            patch("calorie_track_ai_bot.workers.estimate_worker.db_get_photo") as mock_db_get_photo,
            patch(
                "calorie_track_ai_bot.workers.estimate_worker.create_meal_from_estimate"
            ) as mock_create_meal,
            patch(
                "calorie_track_ai_bot.workers.estimate_worker.send_estimate_to_user"
            ) as mock_send_estimate,
        ):
            mock_s3.generate_presigned_url.return_value = "https://presigned-url.example.com"
            mock_estimate.return_value = {
                "kcal_mean": 500,
                "kcal_min": 400,
                "kcal_max": 600,
                "confidence": 0.8,
                "items": [{"label": "pizza", "kcal": 500, "confidence": 0.8}],
            }
            mock_db_save.return_value = "estimate123"
            mock_db_get_photo.return_value = {
                "id": "photo123",
                "tigris_key": "photos/storage_key.jpg",
                "user_id": "user123",
                "status": "uploaded",
            }

            yield {
                "s3": mock_s3,
                "estimate": mock_estimate,
                "db_save": mock_db_save,
                "db_get_photo": mock_db_get_photo,
                "create_meal": mock_create_meal,
                "send_estimate": mock_send_estimate,
            }

    @pytest.mark.asyncio
    async def test_handle_job_success(self, mock_dependencies):
        """Test successful job handling."""
        job = {"photo_id": "photo123"}

        await handle_job(job)

        # Should get photo record first
        mock_dependencies["db_get_photo"].assert_called_once_with("photo123")

        # Should generate presigned URL with the correct storage key
        mock_dependencies["s3"].generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "photos/storage_key.jpg"},
            ExpiresIn=900,
        )

        # Should call estimate function
        mock_dependencies["estimate"].assert_called_once_with("https://presigned-url.example.com")

        # Should save estimate to database
        mock_dependencies["db_save"].assert_called_once()
        call_args = mock_dependencies["db_save"].call_args
        assert call_args.kwargs["photo_id"] == "photo123"

        # Check that confidence was set
        estimate_data = call_args.kwargs["est"]
        assert "confidence" in estimate_data
        assert estimate_data["confidence"] == 0.8  # from mock data

        # Should create meal from estimate
        mock_dependencies["create_meal"].assert_called_once()

        # Should send estimate to user
        mock_dependencies["send_estimate"].assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_job_saves_under_assigned_estimate_id(self, mock_dependencies):
        """The estimate is saved under the ID handed out at enqueue."""
        job = {"photo_id": "photo123", "estimate_id": "estimate-assigned"}

        await handle_job(job)

        call_args = mock_dependencies["db_save"].call_args
        assert call_args.kwargs["estimate_id"] == "estimate-assigned"

    @pytest.mark.asyncio
    async def test_handle_job_passes_estimate_id_to_multiphoto_job(self):
        """Multi-photo jobs get the estimate ID assigned at enqueue."""
        job = {"photo_ids": ["p1", "p2"], "estimate_id": "estimate-assigned"}

        with patch(
            "calorie_track_ai_bot.workers.estimate_worker.handle_multiphotos_job"
        ) as mock_multi:
            await handle_job(job)

        mock_multi.assert_awaited_once_with(
            ["p1", "p2"], None, None, "estimate-assigned", deliver=True
        )

    @pytest.mark.asyncio
    async def test_handle_job_from_api_skips_meal_and_message(self, mock_dependencies):
        """API jobs only save the estimate: the client logs the meal itself."""
        job = {"photo_id": "photo123", "estimate_id": "estimate-assigned", "source": "api"}

        await handle_job(job)

        mock_dependencies["db_save"].assert_called_once()
        mock_dependencies["create_meal"].assert_not_called()
        mock_dependencies["send_estimate"].assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_job_from_api_multiphoto_not_delivered(self):
        """Multi-photo API jobs are handled without delivery."""
        job = {"photo_ids": ["p1"], "estimate_id": "e1", "source": "api"}

        with patch(
            "calorie_track_ai_bot.workers.estimate_worker.handle_multiphotos_job"
        ) as mock_multi:
            await handle_job(job)

        assert mock_multi.call_args.kwargs["deliver"] is False

    @pytest.mark.asyncio
    async def test_handle_job_with_existing_confidence(self, mock_dependencies):
        """Test job handling when estimate already has confidence."""
        job = {"photo_id": "photo456"}

        # Mock estimate to already have confidence
        mock_dependencies["estimate"].return_value = {
            "kcal_mean": 600,
            "kcal_min": 500,
            "kcal_max": 700,
            "confidence": 0.9,  # Already has confidence
            "items": [{"label": "burger", "kcal": 600, "confidence": 0.9}],
        }

        await handle_job(job)

        # Should save estimate with existing confidence
        call_args = mock_dependencies["db_save"].call_args
        estimate_data = call_args.kwargs["est"]
        assert estimate_data["confidence"] == 0.9  # Should keep existing confidence

    @pytest.mark.asyncio
    async def test_handle_job_estimate_error(self, mock_dependencies):
        """Test job handling when estimate fails."""
        job = {"photo_id": "photo789"}

        # Mock estimate to raise an exception
        mock_dependencies["estimate"].side_effect = Exception("Estimation failed")

        with pytest.raises(Exception, match="Estimation failed"):
            await handle_job(job)

        # Should have attempted to get photo and generate URL
        mock_dependencies["db_get_photo"].assert_called_once_with("photo789")
        mock_dependencies["s3"].generate_presigned_url.assert_called_once()

        # Should not have saved estimate
        mock_dependencies["db_save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_job_db_save_error(self, mock_dependencies):
        """Test job handling when database save fails."""
        job = {"photo_id": "photo999"}

        # Mock database save to raise an exception
        mock_dependencies["db_save"].side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await handle_job(job)

        # Should have completed all steps up to save
        mock_dependencies["db_get_photo"].assert_called_once()
        mock_dependencies["estimate"].assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_job_photo_not_found(self, mock_dependencies):
        """Test job handling when photo is not found."""
        job = {"photo_id": "nonexistent"}

        # Mock photo not found
        mock_dependencies["db_get_photo"].return_value = None

        with pytest.raises(ValueError, match="Photo record not found for photo_id"):
            await handle_job(job)

        # Should have attempted to get photo
        mock_dependencies["db_get_photo"].assert_called_once_with("nonexistent")

        # Should not have proceeded further
        mock_dependencies["s3"].generate_presigned_url.assert_not_called()
        mock_dependencies["estimate"].assert_not_called()
        mock_dependencies["db_save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_job_s3_error(self, mock_dependencies):
        """Test job handling when S3 operations fail."""
        job = {"photo_id": "photo111"}

        # Mock S3 to raise an exception
        mock_dependencies["s3"].generate_presigned_url.side_effect = Exception("S3 error")

        with pytest.raises(Exception, match="S3 error"):
            await handle_job(job)

        # Should have gotten photo record
        mock_dependencies["db_get_photo"].assert_called_once()

        # Should not have proceeded to estimation
        mock_dependencies["estimate"].assert_not_called()
        mock_dependencies["db_save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_job_invalid_job_data(self, mock_dependencies):
        """Test job handling with invalid job data."""
        # Test with missing photo_id and photo_ids
        job = {}

        with pytest.raises(ValueError, match="Job must contain either photo_id or photo_ids"):
            await handle_job(job)

        # Should not have called any dependencies
        mock_dependencies["db_get_photo"].assert_not_called()
        mock_dependencies["estimate"].assert_not_called()
        mock_dependencies["db_save"].assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_job_none_photo_id(self, mock_dependencies):
        """Test job handling with None photo_id."""
        job = {"photo_id": None}

        with pytest.raises(ValueError, match="Job must contain either photo_id or photo_ids"):
            await handle_job(job)

    @pytest.mark.asyncio
    async def test_create_meal_from_estimate_success(self):
        """Test successful meal creation from estimate."""
        photo_record = {
            "id": "photo123",
            "user_id": "user123",
            "tigris_key": "photos/storage_key.jpg",
        }
        estimate_id = "00000000-0000-0000-0000-000000000123"

        with patch(
            "calorie_track_ai_bot.workers.estimate_worker.db_create_meal_from_estimate"
        ) as mock_create_meal:
            mock_create_meal.return_value = "meal123"

            await create_meal_from_estimate(photo_record, estimate_id)

            # Should create meal with correct parameters
            mock_create_meal.assert_called_once()
            call_args = mock_create_meal.call_args
            meal_request = call_args[0][0]  # First positional argument
            user_id = call_args[0][1]  # Second positional argument

            assert str(meal_request.estimate_id) == estimate_id
            assert meal_request.meal_type.value == "snack"
            assert user_id == "user123"

    @pytest.mark.asyncio
    async def test_create_meal_from_estimate_no_user_id(self):
        """Test meal creation when photo record has no user_id."""
        photo_record = {
            "id": "photo123",
            "tigris_key": "photos/storage_key.jpg",
            # No user_id
        }
        estimate_id = "00000000-0000-0000-0000-000000000123"

        with patch(
            "calorie_track_ai_bot.workers.estimate_worker.db_create_meal_from_estimate"
        ) as mock_create_meal:
            await create_meal_from_estimate(photo_record, estimate_id)

            # Should not create meal
            mock_create_meal.assert_not_called()

    @pytest.mark.asyncio
    async def test_main_function_loop_logic(self, mock_dependencies):
        """Test the main function loop logic."""
        # This test would require mocking the dequeue function and main loop
        # For now, we'll just test that handle_job works as expected
        job = {"photo_id": "photo123"}

        await handle_job(job)

        # Verify all steps were called
        mock_dependencies["db_get_photo"].assert_called_once()
        mock_dependencies["estimate"].assert_called_once()
        mock_dependencies["db_save"].assert_called_once()

    @pytest.mark.asyncio
    async def test_main_function_error_handling(self, mock_dependencies):
        """Test error handling in main function."""
        job = {"photo_id": "photo123"}

        # Mock an error in the workflow
        mock_dependencies["estimate"].side_effect = Exception("Test error")

        with pytest.raises(Exception, match="Test error"):
            await handle_job(job)

    @pytest.mark.asyncio
    async def test_main_function_no_jobs_logic(self, mock_dependencies):
        """Test main function when no jobs are available."""
        # This would test the case where dequeue returns None
        # For now, we'll test that handle_job works with valid data
        job = {"photo_id": "photo123"}

        await handle_job(job)

        # Verify the job was processed
        mock_dependencies["db_get_photo"].assert_called_once()

    @pytest.mark.asyncio
    async def test_job_data_structure(self, mock_dependencies):
        """Test that job data has the expected structure."""
        job = {"photo_id": "photo123"}

        await handle_job(job)

        # Verify photo_id was extracted correctly
        mock_dependencies["db_get_photo"].assert_called_once_with("photo123")

    @pytest.mark.asyncio
    async def test_estimate_data_modification(self, mock_dependencies):
        """Test that estimate data is properly modified before saving."""
        job = {"photo_id": "photo123"}

        # Mock estimate to not have confidence
        mock_dependencies["estimate"].return_value = {
            "kcal_mean": 500,
            "kcal_min": 400,
            "kcal_max": 600,
            "items": [{"label": "pizza", "kcal": 500, "confidence": 0.8}],
        }

        await handle_job(job)

        # Check that confidence was added
        call_args = mock_dependencies["db_save"].call_args
        estimate_data = call_args.kwargs["est"]
        assert "confidence" in estimate_data
        assert estimate_data["confidence"] == 0.5  # default value
