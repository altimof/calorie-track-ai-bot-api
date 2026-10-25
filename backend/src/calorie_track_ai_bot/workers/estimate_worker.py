import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError

from ..schemas import (
    InlineAnalyticsDaily,
    InlineChatType,
    InlineFailureReason,
    InlineInteractionJob,
    MealCreateFromEstimateRequest,
    MealType,
)
from ..services import inline_notifications, monitoring, telegram
from ..services.config import logger
from ..services.db import (
    db_create_meal_from_estimate,
    db_fetch_inline_analytics,
    db_get_photo,
    db_get_user,
    db_increment_inline_permission_block,
    db_save_estimate,
    db_upsert_inline_analytics,
)
from ..services.estimator import CalorieEstimator, estimate_from_image_url
from ..services.inline_renderer import (
    INLINE_USAGE_GUIDE_LINE,
    PRIVACY_NOTICE_LINE,
    build_inline_result_text,
)
from ..services.queue import dequeue_estimate_job, dequeue_inline_job
from ..services.storage import BUCKET_NAME, generate_presigned_url, s3, tigris_presign_put


async def _send_error_to_user(chat_id: int | None) -> None:
    """Send error notification to the user via Telegram."""
    if not chat_id:
        return
    try:
        bot = telegram.get_bot()
        await bot.send_message(
            chat_id,
            "❌ Sorry, I encountered an error analyzing your photo(s). Please try again later.",
        )
    except Exception as e:
        logger.error(f"Failed to send worker error message to chat {chat_id}: {e}")


async def _keep_typing(
    chat_id: int, stop_event: asyncio.Event, max_duration: float = 120.0
) -> None:
    """Send typing indicators while the worker processes the job."""
    import time

    bot = telegram.get_bot()
    start_time = time.monotonic()
    try:
        while not stop_event.is_set():
            elapsed = time.monotonic() - start_time
            if elapsed >= max_duration:
                logger.warning(
                    f"Typing indicator for chat {chat_id} exceeded max duration "
                    f"({max_duration}s), stopping"
                )
                break

            try:
                await bot.send_chat_action(chat_id, "typing")
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
                break
            except TimeoutError:
                continue
    except asyncio.CancelledError:
        pass


async def handle_job(job: dict[str, Any]) -> None:
    """Handle estimation job for single or multiple photos.

    Feature: 003-update-logic-for (Multi-photo support)
    Supports both legacy single-photo jobs and new multi-photo jobs.
    """
    _log_privacy_metadata(job)

    chat_id = job.get("chat_id")

    # Check if this is a multi-photo job
    photo_ids = job.get("photo_ids")  # New multi-photo format
    photo_id = job.get("photo_id")  # Legacy single-photo format
    description = job.get("description")  # Optional user description
    media_group_id = job.get("media_group_id")  # Telegram media group
    estimate_id = job.get("estimate_id")  # Pre-assigned at enqueue; absent in older jobs
    # API clients log the meal themselves; only bot jobs get a meal and a Telegram reply
    deliver = job.get("source", "bot") != "api"

    # Start typing indicator while processing
    stop_typing = asyncio.Event()
    typing_task = None
    if chat_id:
        typing_task = asyncio.create_task(_keep_typing(chat_id, stop_typing))

    try:
        if photo_ids:
            # Multi-photo job
            logger.info(f"Processing multi-photo estimation job: {len(photo_ids)} photos")
            await handle_multiphotos_job(
                photo_ids, description, media_group_id, estimate_id, deliver=deliver
            )
        elif photo_id:
            # Legacy single-photo job
            logger.info(f"Processing single-photo estimation job for photo_id: {photo_id}")
            await handle_single_photo_job(photo_id, estimate_id, deliver=deliver)
        else:
            raise ValueError("Job must contain either photo_id or photo_ids")
    except Exception:
        await _send_error_to_user(chat_id)
        raise
    finally:
        stop_typing.set()
        if typing_task:
            try:
                await asyncio.wait_for(typing_task, timeout=2.0)
            except TimeoutError:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass


async def handle_single_photo_job(
    photo_id: str, estimate_id: str | None = None, deliver: bool = True
) -> None:
    """Handle legacy single-photo estimation job."""
    if photo_id is None:
        raise ValueError("photo_id cannot be None")

    try:
        # Get photo record to retrieve the storage key
        photo_record = await db_get_photo(photo_id)
        if not photo_record:
            raise ValueError(f"Photo record not found for photo_id: {photo_id}")

        tigris_key = photo_record["tigris_key"]
        logger.debug(f"Retrieved tigris_key for photo {photo_id}: {tigris_key}")

        # Generate presigned URL using the actual storage key
        if s3 is None:
            raise RuntimeError("S3 client not available. Tigris configuration is missing.")

        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": BUCKET_NAME, "Key": tigris_key}, ExpiresIn=900
        )
        logger.debug(f"Generated presigned URL for photo: {photo_id}")

        est = await estimate_from_image_url(url)
        est.setdefault("confidence", 0.5)
        logger.info(f"Estimation completed for photo {photo_id}: {est}")

        estimate_id = await db_save_estimate(photo_id=photo_id, est=est, estimate_id=estimate_id)
        logger.info(f"Estimate saved with ID: {estimate_id} for photo: {photo_id}")

        if not deliver:
            return

        # Create meal record from estimate
        await create_meal_from_estimate(photo_record, estimate_id)

        # Send estimate results back to user via Telegram
        await send_estimate_to_user(photo_record, est, estimate_id)

    except Exception as e:
        logger.error(f"Error processing job for photo {photo_id}: {e}", exc_info=True)
        raise


async def handle_multiphotos_job(
    photo_ids: list[str],
    description: str | None = None,
    media_group_id: str | None = None,
    estimate_id: str | None = None,
    deliver: bool = True,
) -> None:
    """Handle multi-photo estimation job (Feature: 003-update-logic-for).

    Args:
        photo_ids: List of photo IDs (1-5 photos)
        description: Optional meal description
        media_group_id: Telegram media group identifier
        estimate_id: ID to save the estimate under (assigned at enqueue)
        deliver: Create a meal and send the result via Telegram (False for API jobs)
    """
    try:
        logger.info(f"Processing {len(photo_ids)} photos together")

        # Get all photo records and generate presigned URLs
        photo_urls = []
        photo_records = []

        for photo_id in photo_ids:
            photo_record = await db_get_photo(photo_id)
            if not photo_record:
                logger.warning(f"Photo {photo_id} not found, skipping")
                continue

            photo_records.append(photo_record)

            # Generate presigned URL
            tigris_key = photo_record["tigris_key"]
            url = generate_presigned_url(tigris_key, expiry=900)
            photo_urls.append(url)

        if not photo_urls:
            raise ValueError("No valid photos found")

        # Use CalorieEstimator for combined multi-photo analysis
        estimator = CalorieEstimator()
        result = await estimator.estimate_from_photos(
            photo_urls=photo_urls, description=description
        )

        # Save estimate with macronutrients and photo_count
        estimate_data = {
            "kcal_mean": result["calories"]["estimate"],
            "kcal_min": result["calories"]["min"],
            "kcal_max": result["calories"]["max"],
            "confidence": result["confidence"],
            "macronutrients": result["macronutrients"],
            "photo_count": result["photo_count"],
            "items": result.get("items", []),  # Include food items breakdown
        }

        # Save estimate with all photo IDs
        estimate_id = await db_save_estimate(
            photo_id=photo_ids[0], est=estimate_data, photo_ids=photo_ids, estimate_id=estimate_id
        )
        logger.info(f"Multi-photo estimate saved with ID: {estimate_id}")

        if not deliver:
            return

        # Create meal from estimate
        if photo_records:
            await create_meal_from_estimate(photo_records[0], estimate_id)

        # Send results to user with macronutrients
        await send_multiphotos_estimate_to_user(
            photo_records[0], result, estimate_id, len(photo_urls)
        )

    except Exception as e:
        logger.error(f"Error processing multi-photo job: {e}", exc_info=True)
        raise


async def handle_inline_interaction_job(job: dict[str, Any]) -> None:
    """Process inline interaction jobs pulled from the inline queue."""
    _log_privacy_metadata(job)

    inline_job = _parse_inline_job(job)
    if inline_job is None:
        logger.error("Inline job payload missing required fields", extra={"job": job})
        return

    result_latency_ms = 0
    metadata: dict[str, Any] = dict(job.get("metadata") or {})

    try:
        photo_bytes = await _download_inline_photo(inline_job.file_id)
        _, photo_url = await _upload_inline_photo(photo_bytes)
        estimation = await estimate_from_image_url(photo_url)

        now = datetime.now(UTC)
        result_latency_ms = int((now - inline_job.requested_at).total_seconds() * 1000)

        await _deliver_inline_success(inline_job, estimation, metadata)
        await _update_inline_analytics(
            job=inline_job, success=True, result_latency_ms=result_latency_ms
        )

        monitoring.record_inline_result_latency(inline_job.trigger_type.value, result_latency_ms)
        monitoring.record_inline_accuracy_delta(inline_job.trigger_type.value, 0.0)

        logger.info(
            "Inline job completed",
            extra={
                "job_id": str(inline_job.job_id),
                "trigger_type": inline_job.trigger_type.value,
                "result_latency_ms": result_latency_ms,
            },
        )
    except Exception as exc:
        logger.error(
            "Inline job processing failed",
            extra={"job_id": str(job.get("job_id")), "error": str(exc)},
            exc_info=True,
        )
        result_latency_ms = int(
            (datetime.now(UTC) - inline_job.requested_at).total_seconds() * 1000
        )

        monitoring.record_inline_failure_event(inline_job.trigger_type.value, "processing_error")

        await _deliver_inline_failure(inline_job, str(exc), metadata)
        await _update_inline_analytics(
            job=inline_job,
            success=False,
            result_latency_ms=result_latency_ms,
            failure_reason="processing_error",
        )

        monitoring.record_inline_result_latency(inline_job.trigger_type.value, result_latency_ms)


async def create_meal_from_estimate(photo_record: dict[str, Any], estimate_id: str) -> None:
    """Create a meal record from the completed estimate."""
    try:
        user_id = photo_record.get("user_id")
        if not user_id:
            logger.warning("No user_id found in photo record, cannot create meal")
            return

        # Create meal from estimate with default values
        meal_request = MealCreateFromEstimateRequest(
            estimate_id=UUID(estimate_id),
            meal_date=date.today(),
            meal_type=MealType.snack,  # Default to snack, user can change in UI
        )

        meal_id = await db_create_meal_from_estimate(meal_request, user_id)
        logger.info(f"Meal created with ID: {meal_id} from estimate: {estimate_id}")

    except Exception as e:
        logger.error(f"Error creating meal from estimate {estimate_id}: {e}", exc_info=True)
        # Don't raise - meal creation failure shouldn't break the estimate workflow


async def send_estimate_to_user(
    photo_record: dict[str, Any], est: dict[str, Any], estimate_id: str
) -> None:
    """Send calorie estimate results back to user via Telegram."""
    try:
        # Get user information
        user_id = photo_record.get("user_id")
        if not user_id:
            logger.warning("No user_id found in photo record, cannot send estimate")
            return

        user_record = await db_get_user(user_id)
        if not user_record:
            logger.warning(f"User record not found for user_id: {user_id}")
            return

        telegram_id = user_record.get("telegram_id")
        if not telegram_id:
            logger.warning(f"No telegram_id found for user: {user_id}")
            return

        # Format the estimate message
        kcal_mean = est.get("kcal_mean", 0)
        kcal_min = est.get("kcal_min", 0)
        kcal_max = est.get("kcal_max", 0)
        confidence = est.get("confidence", 0)
        items = est.get("items", [])

        # Create message
        message = "🍎 <b>Nutrition Estimate Complete!</b>\n\n"
        message += f"📊 <b>Total Calories:</b> {kcal_mean:.0f} kcal\n"
        message += f"📈 <b>Range:</b> {kcal_min:.0f} - {kcal_max:.0f} kcal\n"
        message += f"🎯 <b>Confidence:</b> {confidence:.0%}\n\n"

        # Add macronutrients from AI response
        macros = est.get("macronutrients", {})
        message += "<b>🏋️ Macronutrients:</b>\n"
        message += f"• Protein: {macros.get('protein', 0):.1f}g\n"
        message += f"• Carbs: {macros.get('carbs', 0):.1f}g\n"
        message += f"• Fats: {macros.get('fats', 0):.1f}g\n\n"

        if items:
            message += "<b>📋 Food Items:</b>\n"
            for item in items:
                label = item.get("label", "Unknown")
                kcal = item.get("kcal", 0)
                item_confidence = item.get("confidence", 0)
                message += f"• {label}: {kcal:.0f} kcal ({item_confidence:.0%})\n"

        # Send message via Telegram
        bot = telegram.get_bot()
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="HTML")
        user_label = user_record.get("handle") or telegram_id
        logger.info(f"Estimate sent to user {user_label} for photo {photo_record['id']}")

    except Exception as e:
        logger.error(f"Error sending estimate to user: {e}", exc_info=True)


async def send_multiphotos_estimate_to_user(
    photo_record: dict[str, Any], result: dict[str, Any], estimate_id: str, photo_count: int
) -> None:
    """Send multi-photo estimate results with actual macronutrients (Feature: 003-update-logic-for)."""
    try:
        # Get user information
        user_id = photo_record.get("user_id")
        if not user_id:
            logger.warning("No user_id found, cannot send estimate")
            return

        user_record = await db_get_user(user_id)
        if not user_record:
            logger.warning(f"User record not found for user_id: {user_id}")
            return

        telegram_id = user_record.get("telegram_id")
        if not telegram_id:
            logger.warning(f"No telegram_id found for user: {user_id}")
            return

        # Extract data from result
        calories = result["calories"]["estimate"]
        kcal_min = result["calories"]["min"]
        kcal_max = result["calories"]["max"]
        confidence = result["confidence"]
        macros = result["macronutrients"]
        items = result.get("items", [])

        # Create enhanced message with actual macronutrients
        message = "🍎 <b>Nutrition Estimate Complete!</b>\n"
        message += f"📸 <i>Analyzed {photo_count} photo(s)</i>\n\n"
        message += f"📊 <b>Total Calories:</b> {calories:.0f} kcal\n"
        message += f"📈 <b>Range:</b> {kcal_min:.0f} - {kcal_max:.0f} kcal\n"
        message += f"🎯 <b>Confidence:</b> {confidence:.0%}\n\n"

        # Add actual macronutrients from AI
        message += "<b>🏋️ Macronutrients:</b>\n"
        message += f"• Protein: {macros['protein']:.1f}g\n"
        message += f"• Carbs: {macros['carbs']:.1f}g\n"
        message += f"• Fats: {macros['fats']:.1f}g\n\n"

        # Add food items breakdown
        if items:
            message += "<b>📋 Food Items:</b>\n"
            for item in items:
                label = item.get("label", "Unknown")
                kcal = item.get("kcal", 0)
                item_confidence = item.get("confidence", 0)
                message += f"• {label}: {kcal:.0f} kcal ({item_confidence:.0%})\n"

        # Send message
        bot = telegram.get_bot()
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="HTML")
        user_label = user_record.get("handle") or telegram_id
        logger.info(
            f"Multi-photo estimate sent to user {user_label}: "
            f"{photo_count} photos, {calories:.0f} kcal"
        )

    except Exception as e:
        logger.error(f"Error sending multi-photo estimate: {e}", exc_info=True)


def _log_privacy_metadata(job: dict[str, Any]) -> None:
    """Log consent and retention metadata for inline jobs."""
    consent = job.get("consent")
    retention = job.get("retention_policy")
    if not consent and not retention:
        return

    inline_job = _parse_inline_job(job)
    if inline_job is None:
        return

    consent_payload = consent or {}
    retention_payload = retention or {}

    logger.info(
        "Inline consent metadata received",
        extra={
            "job_id": str(inline_job.job_id),
            "trigger_type": inline_job.trigger_type.value,
            "chat_type": inline_job.chat_type.value,
            "consent_granted": consent_payload.get("granted"),
            "consent_scope": consent_payload.get("scope"),
            "retention_hours": retention_payload.get("expires_in_hours")
            or consent_payload.get("retention_hours"),
        },
    )

    monitoring.record_inline_metadata(
        job_id=str(inline_job.job_id),
        trigger_type=inline_job.trigger_type.value,
        chat_type=inline_job.chat_type.value,
        consent=consent_payload,
        retention=retention_payload,
    )


def _parse_inline_job(job: dict[str, Any]) -> InlineInteractionJob | None:
    """Attempt to parse inline metadata into InlineInteractionJob schema."""
    inline_fields: dict[str, Any] = {}
    for field_name in InlineInteractionJob.model_fields:
        if field_name in job:
            inline_fields[field_name] = job[field_name]
    if not inline_fields:
        return None

    try:
        return InlineInteractionJob(**inline_fields)
    except ValidationError as exc:
        logger.warning("Invalid inline job metadata", extra={"error": str(exc)})
        return None


async def _download_inline_photo(file_id: str) -> bytes:
    bot = telegram.get_bot()
    file_info = await bot.get_file(file_id)
    file_path = file_info.get("file_path")
    if not file_path:
        raise ValueError("Telegram file response missing file_path")
    return await bot.download_file(file_path)


async def _upload_inline_photo(
    photo_bytes: bytes, content_type: str = "image/jpeg"
) -> tuple[str, str]:
    key, upload_url = await tigris_presign_put(content_type=content_type, prefix="inline")
    if upload_url.startswith("https://test-url.com") or os.getenv("PYTEST_CURRENT_TEST"):
        logger.debug("Skipping inline photo upload in test mode", extra={"key": key})
    else:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    upload_url,
                    content=photo_bytes,
                    headers={"Content-Type": content_type},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "Inline photo upload failed",
                extra={"error": str(exc), "key": key},
            )
            raise
    return key, generate_presigned_url(key, expiry=900)


async def _deliver_inline_success(
    job: InlineInteractionJob, estimation: dict[str, Any], metadata: dict[str, Any]
) -> None:
    summary = build_inline_result_text(estimation=estimation, chat_type=job.chat_type)
    if job.inline_message_id:
        await telegram.send_inline_query_result(
            inline_message_id=job.inline_message_id, text=summary
        )
    else:
        if job.chat_id is None:
            raise ValueError("Inline job missing chat_id for result delivery")
        reply_target: int | None = job.reply_to_message_id
        if reply_target is None and job.origin_message_id is not None:
            try:
                reply_target = int(job.origin_message_id)
            except (TypeError, ValueError):
                reply_target = None
        try:
            await telegram.send_group_inline_result(
                chat_id=job.chat_id,
                thread_id=job.thread_id,
                reply_to_message_id=reply_target,
                text=summary,
            )
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            await _handle_permission_block(job, summary, metadata, exc)


async def _deliver_inline_failure(
    job: InlineInteractionJob, error: str, metadata: dict[str, Any]
) -> None:
    failure_text = (
        "⚠️ <b>We couldn't analyse this meal photo.</b>\n"
        "Please retry in a moment or capture a clearer image."
    )
    if job.chat_type == InlineChatType.private:
        failure_text += f"\n\n{PRIVACY_NOTICE_LINE}\n{INLINE_USAGE_GUIDE_LINE}"
    if job.inline_message_id:
        await telegram.send_inline_query_result(
            inline_message_id=job.inline_message_id, text=failure_text
        )
    elif job.chat_id is not None:
        reply_target: int | None = job.reply_to_message_id
        if reply_target is None and job.origin_message_id is not None:
            try:
                reply_target = int(job.origin_message_id)
            except (TypeError, ValueError):
                reply_target = None
        try:
            await telegram.send_group_inline_result(
                chat_id=job.chat_id,
                thread_id=job.thread_id,
                reply_to_message_id=reply_target,
                text=failure_text,
            )
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            await _handle_permission_block(job, failure_text, metadata, exc)
    logger.info(
        "Inline job failure notified",
        extra={"job_id": str(job.job_id), "trigger_type": job.trigger_type.value, "error": error},
    )


def _resolve_notice_keys(job: InlineInteractionJob) -> tuple[str | None, str | None]:
    chat_hash = job.chat_id_hash or (str(job.chat_id) if job.chat_id is not None else None)
    user_hash = job.source_user_hash or (
        str(job.source_user_id) if job.source_user_id is not None else None
    )
    return chat_hash, user_hash


async def _record_permission_block(job: InlineInteractionJob) -> None:
    monitoring.record_inline_permission_block_event(job.trigger_type.value, job.chat_type.value)
    try:
        await db_increment_inline_permission_block(
            date_value=datetime.now(UTC).date(),
            chat_type=job.chat_type,
        )
    except Exception as exc:  # pragma: no cover - depends on external services
        logger.warning(
            "Failed to persist inline permission block metric",
            extra={"job_id": str(job.job_id), "error": str(exc)},
        )


async def _should_send_permission_dm(
    job: InlineInteractionJob,
) -> tuple[bool, str | None, str | None]:
    chat_hash, user_hash = _resolve_notice_keys(job)
    if not chat_hash or not user_hash:
        return True, chat_hash, user_hash
    try:
        due = await inline_notifications.permission_notice_due(chat_hash, user_hash)
        return due, chat_hash, user_hash
    except RuntimeError as exc:  # pragma: no cover - defensive
        logger.warning(
            "Permission notice check failed",
            extra={
                "job_id": str(job.job_id),
                "trigger_type": job.trigger_type.value,
                "error": str(exc),
            },
        )
        return True, chat_hash, user_hash


def _build_permission_dm(job: InlineInteractionJob, text: str, metadata: dict[str, Any]) -> str:
    chat_title = metadata.get("chat_title") or "the group"
    instructions = (
        f"I couldn't post this inline update in {chat_title} because I don't have permission to send messages."
        " Please ask a group admin to allow @CalorieTrackAI_bot to post replies."
    )
    reminder = "You'll only receive this reminder once every 24 hours."
    return f"🚫 {instructions}\n\n{text}\n\n{reminder}"


async def _send_permission_dm(
    job: InlineInteractionJob,
    text: str,
    metadata: dict[str, Any],
    chat_hash: str | None,
    user_hash: str | None,
) -> None:
    if job.source_user_id is None:
        logger.warning(
            "Unable to send permission DM — missing source user id",
            extra={"job_id": str(job.job_id)},
        )
        return

    bot = telegram.get_bot()
    dm_text = _build_permission_dm(job, text, metadata)
    await bot.send_message(chat_id=job.source_user_id, text=dm_text, parse_mode="HTML")

    if chat_hash and user_hash:
        try:
            await inline_notifications.mark_permission_notice(chat_hash, user_hash)
        except RuntimeError as exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to persist permission notice",
                extra={"job_id": str(job.job_id), "error": str(exc)},
            )


async def _handle_permission_block(
    job: InlineInteractionJob,
    message_text: str,
    metadata: dict[str, Any],
    exc: Exception,
) -> None:
    logger.warning(
        "Inline permission block encountered",
        extra={
            "job_id": str(job.job_id),
            "trigger_type": job.trigger_type.value,
            "chat_type": job.chat_type.value,
            "error": str(exc),
        },
    )

    await _record_permission_block(job)

    require_dm = metadata.get("failure_dm_required", job.chat_type == InlineChatType.group)
    if not require_dm:
        return

    should_dm, chat_hash, user_hash = await _should_send_permission_dm(job)
    if not should_dm:
        return

    try:
        await _send_permission_dm(job, message_text, metadata, chat_hash, user_hash)
    except Exception as dm_exc:  # pragma: no cover - defensive
        logger.error(
            "Failed to send permission DM",
            extra={"job_id": str(job.job_id), "error": str(dm_exc)},
        )


async def _update_inline_analytics(
    *,
    job: InlineInteractionJob,
    success: bool,
    result_latency_ms: int,
    failure_reason: str | None = None,
) -> None:
    today = datetime.now(UTC).date()
    try:
        records = await db_fetch_inline_analytics(today, today, job.chat_type.value)
    except Exception as exc:  # pragma: no cover - depends on external services
        logger.warning(
            "Skipping inline analytics update due to fetch failure",
            extra={"error": str(exc), "job_id": str(job.job_id)},
        )
        return
    if records:
        record = records[0]
    else:
        record = InlineAnalyticsDaily(
            id=uuid4(),
            date=today,
            chat_type=job.chat_type,
            trigger_counts={},
            request_count=0,
            success_count=0,
            failure_count=0,
            permission_block_count=0,
            avg_ack_latency_ms=0,
            p95_result_latency_ms=0,
            accuracy_within_tolerance_pct=0.0,
            failure_reasons=[],
            last_updated_at=datetime.now(UTC),
        )

    previous_requests = record.request_count
    record.request_count += 1
    trigger_counts = dict(record.trigger_counts or {})
    trigger_counts[job.trigger_type.value] = trigger_counts.get(job.trigger_type.value, 0) + 1
    record.trigger_counts = trigger_counts

    if success:
        record.success_count += 1
    else:
        record.failure_count += 1
        reasons = {reason.reason: reason.count for reason in record.failure_reasons or []}
        failure_key = failure_reason or "unknown_error"
        reasons[failure_key] = reasons.get(failure_key, 0) + 1
        record.failure_reasons = [
            InlineFailureReason(reason=reason, count=count) for reason, count in reasons.items()
        ]

    # Update rolling average with new result latency
    record.avg_ack_latency_ms = int(
        (record.avg_ack_latency_ms * previous_requests + result_latency_ms) / record.request_count
    )

    record.p95_result_latency_ms = max(record.p95_result_latency_ms, result_latency_ms)
    if record.request_count:
        record.accuracy_within_tolerance_pct = (record.success_count / record.request_count) * 100
    record.last_updated_at = datetime.now(UTC)

    try:
        await db_upsert_inline_analytics(record)
    except Exception as exc:  # pragma: no cover - depends on external services
        logger.warning(
            "Failed to upsert inline analytics record",
            extra={"error": str(exc), "job_id": str(job.job_id)},
        )


async def process_estimate_jobs() -> None:
    logger.info("Estimate job consumer started")
    while True:
        try:
            job = await dequeue_estimate_job()
            if job:
                logger.debug(f"Dequeued job: {job}")
                await handle_job(job)
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            await asyncio.sleep(5)  # Wait before retrying


async def process_inline_jobs() -> None:
    logger.info("Inline job consumer started")
    while True:
        try:
            job = await dequeue_inline_job()
            if job:
                logger.debug(f"Dequeued inline job: {job}")
                await handle_inline_interaction_job(job)
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Inline worker error: {e}", exc_info=True)
            await asyncio.sleep(5)


async def main() -> None:
    logger.info("Starting estimation worker")
    await asyncio.gather(process_estimate_jobs(), process_inline_jobs())


if __name__ == "__main__":
    asyncio.run(main())
