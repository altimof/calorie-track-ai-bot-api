"""Tests for queue module."""

import hmac
import json
from hashlib import sha256
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from calorie_track_ai_bot.services import queue as queue_module
from calorie_track_ai_bot.services.queue import (
    INLINE_BURST_KEY,
    INLINE_MINUTE_KEY,
    INLINE_QUEUE,
    QUEUE,
    InlineChatType,
    InlineQueueThrottleError,
    InlineTriggerType,
    dequeue_estimate_job,
    dequeue_inline_job,
    enqueue_estimate_job,
    enqueue_inline_job,
)


class TestQueueFunctions:
    """Test queue functions."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch("calorie_track_ai_bot.services.queue.r") as mock_r:
            # Create a mock that can be configured per test
            mock_r.lpush = AsyncMock()
            mock_r.brpop = AsyncMock()
            mock_r.pipeline = Mock()
            mock_r.decr = AsyncMock()
            yield mock_r

    @pytest.mark.asyncio
    async def test_enqueue_estimate_job(self, mock_redis):
        """Test enqueuing an estimate job."""
        photo_id = "photo123"

        async def mock_lpush(queue, data):
            return 1

        mock_redis.lpush.side_effect = mock_lpush

        result = await enqueue_estimate_job(photo_id)

        # Should call lpush with correct parameters
        mock_redis.lpush.assert_called_once()
        call_args = mock_redis.lpush.call_args

        assert call_args[0][0] == QUEUE
        job_data = json.loads(call_args[0][1])
        assert job_data["photo_ids"] == [photo_id]

        # Should return the estimate ID the worker will save the estimate under
        assert result == job_data["estimate_id"]
        assert str(UUID(result)) == result

    @pytest.mark.asyncio
    async def test_enqueue_estimate_job_with_uuid(self, mock_redis):
        """Test enqueuing an estimate job with UUID photo_id."""
        photo_id = "550e8400-e29b-41d4-a716-446655440000"

        async def mock_lpush(queue, data):
            return 1

        mock_redis.lpush.side_effect = mock_lpush

        result = await enqueue_estimate_job(photo_id)

        # Should call lpush with correct parameters
        call_args = mock_redis.lpush.call_args
        job_data = json.loads(call_args[0][1])
        assert job_data["photo_ids"] == [photo_id]

        # The estimate ID is new, not the photo ID
        assert result == job_data["estimate_id"]
        assert result != photo_id

    @pytest.mark.asyncio
    async def test_dequeue_estimate_job_with_data(self, mock_redis):
        """Test dequeuing an estimate job when data is available."""
        job_data = {"photo_ids": ["photo456"]}

        async def mock_brpop(queue, timeout):
            return ("estimate_jobs", json.dumps(job_data))

        mock_redis.brpop.side_effect = mock_brpop

        result = await dequeue_estimate_job()

        # Should return the parsed job data
        assert result == job_data

        # Should call brpop with correct parameters
        mock_redis.brpop.assert_called_once_with([QUEUE], timeout=10)

    @pytest.mark.asyncio
    async def test_dequeue_estimate_job_no_data(self, mock_redis):
        """Test dequeuing an estimate job when no data is available."""

        async def mock_brpop(queue, timeout):
            return None

        mock_redis.brpop.side_effect = mock_brpop

        result = await dequeue_estimate_job()

        # Should return None
        assert result is None

        # Should call brpop with correct parameters
        mock_redis.brpop.assert_called_once_with([QUEUE], timeout=10)

    @pytest.mark.asyncio
    async def test_dequeue_estimate_job_empty_list(self, mock_redis):
        """Test dequeuing an estimate job when brpop returns empty list."""

        async def mock_brpop(queue, timeout):
            return []

        mock_redis.brpop.side_effect = mock_brpop

        result = await dequeue_estimate_job()

        # Should return None (empty list means no data)
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_estimate_job_invalid_json(self, mock_redis):
        """Test dequeuing an estimate job with invalid JSON."""

        async def mock_brpop(queue, timeout):
            return ("estimate_jobs", "invalid json")

        mock_redis.brpop.side_effect = mock_brpop

        # Should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            await dequeue_estimate_job()

    @pytest.mark.asyncio
    async def test_dequeue_estimate_job_redis_error(self, mock_redis):
        """Test dequeuing an estimate job when Redis raises an error."""
        mock_redis.brpop.side_effect = Exception("Redis connection error")

        # Should propagate the exception
        with pytest.raises(Exception, match="Redis connection error"):
            await dequeue_estimate_job()

    @pytest.mark.asyncio
    async def test_enqueue_estimate_job_redis_error(self, mock_redis):
        """Test enqueuing an estimate job when Redis raises an error."""
        mock_redis.lpush.side_effect = Exception("Redis connection error")

        # Should propagate the exception
        with pytest.raises(Exception, match="Redis connection error"):
            await enqueue_estimate_job("photo123")

    def test_queue_constant(self):
        """Test that QUEUE constant is set correctly."""
        assert QUEUE == "estimate_jobs"

    @pytest.mark.asyncio
    async def test_job_data_structure(self, mock_redis):
        """Test that job data has the correct structure."""
        photo_id = "test_photo_123"

        async def mock_lpush(queue, data):
            return 1

        mock_redis.lpush.side_effect = mock_lpush

        await enqueue_estimate_job(photo_id)

        # Get the job data that was enqueued
        call_args = mock_redis.lpush.call_args
        job_data = json.loads(call_args[0][1])

        # Should have photo_ids field
        assert "photo_ids" in job_data
        assert job_data["photo_ids"] == [photo_id]

        # Should be a valid JSON structure
        assert isinstance(job_data, dict)
        assert set(job_data) == {"photo_ids", "description", "estimate_id", "source"}
        assert job_data["source"] == "bot"

    @pytest.mark.asyncio
    async def test_round_trip_job_processing(self, mock_redis):
        """Test complete round trip of job enqueue/dequeue."""
        photo_id = "roundtrip_photo_456"

        async def mock_lpush(queue, data):
            return 1

        mock_redis.lpush.side_effect = mock_lpush

        # Enqueue a job
        await enqueue_estimate_job(photo_id)

        # Get the job data that was enqueued
        enqueue_call_args = mock_redis.lpush.call_args
        job_data = json.loads(enqueue_call_args[0][1])

        # Mock the dequeue to return this same data
        async def mock_brpop(queue, timeout):
            return ("estimate_jobs", json.dumps(job_data))

        mock_redis.brpop.side_effect = mock_brpop

        # Dequeue the job
        result = await dequeue_estimate_job()

        # Should get back the same data
        assert result == job_data
        assert result["photo_ids"] == [photo_id]

    @pytest.mark.asyncio
    async def test_enqueue_inline_job_hashes_identifiers(self, mock_redis):
        """Inline enqueue should hash identifiers and include consent metadata."""
        mock_redis.pipeline.return_value = PipelineStub([1, True, 1, True])

        # Ensure hash salt configured
        original_salt = queue_module.INLINE_HASH_SALT
        original_min = queue_module.INLINE_THROUGHPUT_PER_MIN
        original_burst = queue_module.INLINE_BURST_RPS
        try:
            queue_module.INLINE_HASH_SALT = "unit-test-salt"
            queue_module._salt_warning_emitted = False
            queue_module.INLINE_THROUGHPUT_PER_MIN = 5
            queue_module.INLINE_BURST_RPS = 5

            job_id = uuid4()

            await enqueue_inline_job(
                job_id=job_id,
                trigger_type=InlineTriggerType.inline_query,
                chat_type=InlineChatType.private,
                file_id="abc123",
                raw_chat_id=12345,
                raw_user_id=67890,
                consent_granted=True,
                consent_scope="inline_processing",
                consent_reference="consent-42",
                retention_hours=12,
                metadata={"origin": "test"},
            )

            mock_redis.lpush.assert_called_once()
            queue_name, payload = mock_redis.lpush.call_args[0]
            assert queue_name == INLINE_QUEUE

            job_payload = json.loads(payload)
            expected_chat_hash = hmac.new(
                queue_module.INLINE_HASH_SALT.encode(),
                str(12345).encode(),
                sha256,
            ).hexdigest()
            expected_user_hash = hmac.new(
                queue_module.INLINE_HASH_SALT.encode(),
                str(67890).encode(),
                sha256,
            ).hexdigest()
            assert job_payload["chat_id_hash"] == expected_chat_hash
            assert job_payload["source_user_hash"] == expected_user_hash
            assert job_payload["consent"]["granted"] is True
            assert job_payload["consent"]["scope"] == "inline_processing"
            assert job_payload["consent"]["reference"] == "consent-42"
            assert job_payload["consent"]["retention_hours"] == 12
            assert job_payload["retention_policy"]["expires_in_hours"] == 12
            assert job_payload["metadata"] == {"origin": "test"}
            assert job_payload["trigger_type"] == InlineTriggerType.inline_query.value
        finally:
            queue_module.INLINE_HASH_SALT = original_salt
            queue_module.INLINE_THROUGHPUT_PER_MIN = original_min
            queue_module.INLINE_BURST_RPS = original_burst
            queue_module._salt_warning_emitted = False

    @pytest.mark.asyncio
    async def test_enqueue_inline_job_rate_limit_exceeded(self, mock_redis):
        """Inline enqueue should enforce throughput limits."""
        original_salt = queue_module.INLINE_HASH_SALT
        original_min = queue_module.INLINE_THROUGHPUT_PER_MIN
        original_burst = queue_module.INLINE_BURST_RPS
        try:
            queue_module.INLINE_HASH_SALT = "unit-test-salt"
            queue_module._salt_warning_emitted = False
            queue_module.INLINE_THROUGHPUT_PER_MIN = 1
            queue_module.INLINE_BURST_RPS = 1

            mock_redis.pipeline.return_value = PipelineStub([2, True, 2, True])

            with pytest.raises(InlineQueueThrottleError):
                await enqueue_inline_job(
                    job_id=uuid4(),
                    trigger_type=InlineTriggerType.inline_query,
                    chat_type=InlineChatType.private,
                    file_id="abc123",
                    raw_chat_id=1,
                    raw_user_id=2,
                )

            mock_redis.decr.assert_any_call(INLINE_MINUTE_KEY)
            mock_redis.decr.assert_any_call(INLINE_BURST_KEY)
        finally:
            queue_module.INLINE_HASH_SALT = original_salt
            queue_module.INLINE_THROUGHPUT_PER_MIN = original_min
            queue_module.INLINE_BURST_RPS = original_burst
            queue_module._salt_warning_emitted = False

    @pytest.mark.asyncio
    async def test_dequeue_inline_job_returns_payload(self, mock_redis):
        """Inline dequeue should parse payload."""
        job_payload = {"job_id": "123", "trigger_type": "inline_query"}

        async def mock_brpop(queue, timeout):
            return (INLINE_QUEUE, json.dumps(job_payload))

        mock_redis.brpop.side_effect = mock_brpop

        result = await dequeue_inline_job()
        assert result == job_payload
        mock_redis.brpop.assert_called_once_with([INLINE_QUEUE], timeout=10)


class PipelineStub:
    """Simple pipeline stub for Redis rate limit tests."""

    def __init__(self, results):
        self.results = results

    def incr(self, *_args, **_kwargs):
        return self

    def expire(self, *_args, **_kwargs):
        return self

    async def execute(self):
        return self.results
