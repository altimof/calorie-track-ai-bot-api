import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from ..schemas import InlineChatType, InlineInteractionJob, InlineTriggerType
from .config import (
    APP_ENV,
    INLINE_BURST_RPS,
    INLINE_HASH_SALT,
    INLINE_THROUGHPUT_PER_MIN,
    REDIS_URL,
    logger,
)

# Initialize Redis client only if configuration is available
r: redis.Redis | None = None
QUEUE = "estimate_jobs"
INLINE_QUEUE = "inline_jobs"
INLINE_MINUTE_KEY = "inline:throttle:minute"
INLINE_BURST_KEY = "inline:throttle:burst"
INLINE_RETENTION_HOURS_DEFAULT = 24

if REDIS_URL is not None:
    r = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        health_check_interval=30,
        socket_connect_timeout=5,
        socket_timeout=30,
        retry=Retry(ExponentialBackoff(), 3),
        retry_on_error=[redis.ConnectionError, redis.TimeoutError],
    )
elif APP_ENV == "dev":
    # In development mode, allow missing Redis config
    print("WARNING: Redis configuration not set. Queue functionality will be disabled.")
    print("To enable queue operations, set the following environment variable:")
    print("- REDIS_URL")
else:
    raise ValueError("REDIS_URL must be set")


async def enqueue_estimate_job(
    photo_ids: str | list[str],
    description: str | None = None,
    chat_id: int | None = None,
    telegram_id: int | None = None,
    source: str = "bot",
) -> str:
    """Enqueue an estimation job for one or more photos.

    Args:
        photo_ids: Single photo ID or list of photo IDs
        description: Optional user-provided meal description
        chat_id: Telegram chat ID for sending results/errors back
        telegram_id: Telegram user ID for user identification
        source: "bot" to log a meal and message the user when done; "api" when the
            client logs the meal itself (POST /meals) and polls for the estimate

    Returns:
        ID the worker saves the estimate under; GET /estimates/{id} returns 404
        until the estimate is done.
    """
    if r is None:
        raise RuntimeError("Redis configuration not available. Queue functionality is disabled.")

    # Normalize to list
    if isinstance(photo_ids, str):
        photo_ids = [photo_ids]

    estimate_id = str(uuid4())
    job: dict[str, Any] = {
        "photo_ids": photo_ids,
        "description": description,
        "estimate_id": estimate_id,
        "source": source,
    }
    if chat_id is not None:
        job["chat_id"] = chat_id
    if telegram_id is not None:
        job["telegram_id"] = telegram_id
    await r.lpush(QUEUE, json.dumps(job))  # type: ignore

    return estimate_id


async def dequeue_estimate_job() -> dict[str, Any] | None:
    if r is None:
        raise RuntimeError("Redis configuration not available. Queue functionality is disabled.")

    res = await r.brpop([QUEUE], timeout=10)  # type: ignore
    if res:
        _key, data = res
        return json.loads(data)
    return None


class InlineQueueThrottleError(RuntimeError):
    """Raised when inline queue throughput exceeds configured limits."""


_salt_warning_emitted = False


def _hash_identifier(raw_value: str | int | None) -> str | None:
    """Hash chat/user identifiers using the configured inline salt."""
    global _salt_warning_emitted
    if raw_value in (None, ""):
        return None

    if not INLINE_HASH_SALT:
        if not _salt_warning_emitted:
            logger.warning(
                "INLINE_HASH_SALT is not configured; inline identifiers will not be hashed."
            )
            _salt_warning_emitted = True
        return None

    value_bytes = str(raw_value).encode("utf-8")
    digest = hmac.new(INLINE_HASH_SALT.encode("utf-8"), value_bytes, hashlib.sha256).hexdigest()
    return digest


async def _execute_pipeline(pipeline: Any) -> list[Any]:
    """Execute a Redis pipeline and return results."""
    result = pipeline.execute()
    if hasattr(result, "__await__"):
        result = await result  # type: ignore[assignment]
    return list(result)


async def _enforce_inline_rate_limits() -> None:
    """Ensure inline enqueues honor configured throughput limits."""
    if r is None:
        raise RuntimeError("Redis configuration not available. Queue functionality is disabled.")

    pipeline = r.pipeline()
    pipeline.incr(INLINE_MINUTE_KEY)
    pipeline.expire(INLINE_MINUTE_KEY, 60)
    pipeline.incr(INLINE_BURST_KEY)
    pipeline.expire(INLINE_BURST_KEY, 1)
    results = await _execute_pipeline(pipeline)

    minute_count = results[0] if len(results) > 0 else 0
    burst_count = results[2] if len(results) > 2 else 0

    if minute_count > INLINE_THROUGHPUT_PER_MIN or burst_count > INLINE_BURST_RPS:
        # Roll back increments to keep counters accurate
        await r.decr(INLINE_MINUTE_KEY)  # type: ignore[func-returns-value]
        await r.decr(INLINE_BURST_KEY)  # type: ignore[func-returns-value]
        raise InlineQueueThrottleError(
            "Inline queue throughput exceeded configured limits "
            f"(minute={minute_count}, burst={burst_count})"
        )


async def enqueue_inline_job(
    *,
    job_id: UUID | str,
    trigger_type: InlineTriggerType,
    chat_type: InlineChatType,
    file_id: str,
    raw_chat_id: int | str | None = None,
    raw_user_id: int | str | None = None,
    inline_message_id: str | None = None,
    reply_to_message_id: int | None = None,
    thread_id: int | None = None,
    origin_message_id: str | None = None,
    consent_granted: bool = True,
    consent_scope: str = "inline_processing",
    consent_reference: str | None = None,
    retention_hours: int = INLINE_RETENTION_HOURS_DEFAULT,
    metadata: dict[str, Any] | None = None,
    throttle: bool = True,
) -> str:
    """
    Enqueue an inline interaction job with hashed identifiers and consent metadata.

    Args:
        job_id: Unique job identifier.
        trigger_type: Inline trigger type.
        chat_type: Type of chat initiating the job.
        file_id: Telegram file identifier.
        raw_chat_id: Raw chat identifier for hashing (not persisted).
        raw_user_id: Raw user identifier for hashing (not persisted).
        inline_message_id: Target inline message for updates.
        reply_to_message_id: Original message ID for threaded replies.
        thread_id: Telegram thread/topic identifier.
        origin_message_id: Identifier of forwarded/original message for logging purposes.
        consent_granted: Whether user consent covers inline processing.
        consent_scope: Consent scope label propagated to workers.
        consent_reference: Consent record identifier (e.g., database row ID).
        retention_hours: Hour window before transient artifacts must be purged.
        metadata: Additional metadata to propagate with the job.
        throttle: Skip rate-limit enforcement when False (e.g., backfill jobs).

    Returns:
        str: The enqueued job identifier.
    """
    if r is None:
        raise RuntimeError("Redis configuration not available. Queue functionality is disabled.")

    job_uuid = UUID(str(job_id))

    if throttle:
        await _enforce_inline_rate_limits()

    job = InlineInteractionJob(
        job_id=job_uuid,
        trigger_type=trigger_type,
        chat_type=chat_type,
        chat_id=int(raw_chat_id) if raw_chat_id is not None else None,
        chat_id_hash=_hash_identifier(raw_chat_id),
        thread_id=thread_id,
        reply_to_message_id=reply_to_message_id,
        inline_message_id=inline_message_id,
        file_id=file_id,
        origin_message_id=origin_message_id,
        source_user_id=int(raw_user_id) if raw_user_id is not None else None,
        source_user_hash=_hash_identifier(raw_user_id),
        requested_at=datetime.now(UTC),
    )

    payload = job.model_dump(mode="json")
    payload["consent"] = {
        "granted": consent_granted,
        "scope": consent_scope,
        "reference": consent_reference,
        "captured_at": datetime.now(UTC).isoformat(),
        "retention_hours": retention_hours,
    }
    payload["retention_policy"] = {"expires_in_hours": retention_hours}
    if metadata:
        payload["metadata"] = metadata

    await r.lpush(INLINE_QUEUE, json.dumps(payload))  # type: ignore
    logger.debug(
        "Inline job enqueued",
        extra={
            "job_id": str(job_uuid),
            "trigger_type": trigger_type.value,
            "chat_type": chat_type.value,
        },
    )
    return str(job_uuid)


async def dequeue_inline_job(timeout: int = 10) -> dict[str, Any] | None:
    """Retrieve the next inline interaction job from the queue."""
    if r is None:
        raise RuntimeError("Redis configuration not available. Queue functionality is disabled.")

    res = await r.brpop([INLINE_QUEUE], timeout=timeout)  # type: ignore
    if not res:
        return None

    _key, data = res
    return json.loads(data)
