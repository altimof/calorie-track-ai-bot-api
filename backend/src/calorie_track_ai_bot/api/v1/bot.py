import asyncio
import hmac
import json
import re
import time
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...schemas import InlineChatType, InlineTriggerType
from ...services import telegram
from ...services.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_SECRET,
    USE_WEBHOOK,
    WEBHOOK_URL,
    logger,
)
from ...services.db import db_create_photo, db_get_or_create_user
from ...services.inline_renderer import build_inline_placeholder
from ...services.queue import InlineQueueThrottleError, enqueue_estimate_job, enqueue_inline_job
from ...services.storage import tigris_presign_put

router = APIRouter()

# Media group aggregation: {media_group_id: {photos: [], caption: str, task: Task}}
media_groups: dict[str, dict[str, Any]] = {}

# Time-based photo grouping for photos without media_group_id
# {user_id: {photos: [], timestamp: float, task: Task, message_ids: []}}
user_photo_groups: dict[str, dict[str, Any]] = {}

# Track recent photo messages to detect rapid-fire uploads
# {user_id: [message_data]}
recent_photo_messages: dict[str, list[dict[str, Any]]] = {}

# Track groups currently being processed to prevent duplicate responses
processing_groups: set[str] = set()

BOT_USERNAME = "@calorietrackai_bot"


def get_bot() -> Any:
    """Expose Telegram bot accessor for compatibility with legacy tests."""
    return telegram.get_bot()


async def send_inline_query_acknowledgement(**kwargs: Any) -> Any:
    """Proxy wrapper for acknowledgement responses."""
    return await telegram.send_inline_query_acknowledgement(**kwargs)


async def send_group_inline_placeholder(**kwargs: Any) -> Any:
    """Proxy wrapper for inline placeholders."""
    return await telegram.send_group_inline_placeholder(**kwargs)


async def send_group_inline_result(**kwargs: Any) -> Any:
    """Proxy wrapper for inline result delivery."""
    return await telegram.send_group_inline_result(**kwargs)


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _derive_public_job_id(seed: str | None) -> str | None:
    if not seed:
        return None
    slug = _NON_ALNUM.sub("-", seed.lower()).strip("-")
    if not slug:
        return None
    if slug.startswith("file-"):
        slug = slug[5:]
    slug = re.sub(r"-\d+$", "", slug)
    if not slug:
        return None
    return f"job-inline-{slug}"


def _resolve_public_job_id(*, requested_job_id: UUID, queue_job_id: str, seed: str | None) -> str:
    hinted = _derive_public_job_id(seed)
    if hinted and queue_job_id == str(requested_job_id):
        return hinted
    return queue_job_id


class TelegramUpdate(BaseModel):
    update_id: int
    message: dict[str, Any] | None = None


class TelegramMessage(BaseModel):
    message_id: int
    from_user: dict[str, Any] | None = Field(None, alias="from")
    chat: dict[str, Any] | None = None
    date: int
    text: str | None = None
    photo: list[dict[str, Any]] | None = None
    caption: str | None = None
    media_group_id: str | None = None
    entities: list[dict[str, Any]] | None = None
    caption_entities: list[dict[str, Any]] | None = None
    reply_to_message: dict[str, Any] | None = None
    message_thread_id: int | None = None


def _normalize_chat_type(raw: str | None) -> InlineChatType:
    if raw in {"group", "supergroup"}:
        return InlineChatType.group
    return InlineChatType.private


def _mentions_bot(text: str | None, entities: list[dict[str, Any]] | None) -> bool:
    if not text or not entities:
        return False

    lowered = text.lower()
    target = BOT_USERNAME.lower()
    for entity in entities:
        if entity.get("type") in {"mention", "text_mention"}:
            offset = entity.get("offset", 0)
            length = entity.get("length", 0)
            mention = lowered[offset : offset + length]
            if mention == target:
                return True
            if lowered.startswith(target, offset):
                return True
    return False


def _best_photo_file_id(photos: list[dict[str, Any]] | None) -> str | None:
    if not photos:
        return None

    sorted_photos = sorted(
        photos,
        key=lambda item: (
            item.get("file_size", 0),
            item.get("width", 0),
            item.get("height", 0),
        ),
        reverse=True,
    )
    return sorted_photos[0].get("file_id")


def _is_inline_reply(message: TelegramMessage) -> bool:
    if not message.reply_to_message:
        return False

    chat_type = (message.chat or {}).get("type")
    if chat_type not in {"group", "supergroup"}:
        return False

    has_photo = bool(message.reply_to_message.get("photo"))
    if not has_photo:
        return False

    return _mentions_bot(message.text, message.entities)


def _is_tagged_inline_photo(message: TelegramMessage) -> bool:
    if not message.photo:
        return False

    chat_type = (message.chat or {}).get("type")
    if chat_type not in {"group", "supergroup"}:
        return False

    if _mentions_bot(message.caption, message.caption_entities):
        return True

    # Some clients include mention in text entities even with caption
    return _mentions_bot(message.caption, message.entities)


def _parse_inline_query_payload(raw_query: str | None) -> dict[str, Any]:
    if not raw_query:
        return {}

    stripped = raw_query.strip()
    if not stripped:
        return {}

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        logger.warning("Inline query payload is not valid JSON: %s", raw_query)
        return {}


async def send_inline_query_help(inline_query_id: str) -> None:
    """Send helpful article results when user invokes inline mode without a photo."""
    bot = telegram.get_bot()

    # Create article result with instructions
    results = [
        {
            "type": "article",
            "id": "help-1",
            "title": "📸 How to use Inline Mode",
            "description": "Learn how to analyze photos using inline mode",
            "input_message_content": {
                "message_text": (
                    "🤖 <b>How to use Calorie Track AI in Inline Mode:</b>\n\n"
                    "1️⃣ Send a photo to a group chat or channel\n"
                    "2️⃣ Reply to that photo and mention me: @calorietrackai_bot\n"
                    "3️⃣ I'll analyze the photo and provide calorie estimates!\n\n"
                    "Or tag me in your photo caption in group chats:\n"
                    "<code>@calorietrackai_bot [your photo]</code>\n\n"
                    "💡 For private calorie tracking, send photos directly to me!"
                ),
                "parse_mode": "HTML",
            },
        }
    ]

    try:
        await bot.answer_inline_query(
            inline_query_id=inline_query_id,
            results=results,
            cache_time=300,  # Cache for 5 minutes
            is_personal=True,
        )
        logger.info(f"Sent help results for inline query {inline_query_id}")
    except Exception as e:
        logger.error(f"Failed to send inline query help: {e}", exc_info=True)


async def handle_inline_query(inline_query: dict[str, Any]) -> dict[str, Any]:
    """Handle Telegram inline query updates for inline photo analysis."""
    user = inline_query.get("from", {})
    payload = _parse_inline_query_payload(inline_query.get("query"))

    file_id = payload.get("file_id")
    if not file_id:
        # When query is empty or missing file_id, send helpful placeholder results
        inline_query_id = inline_query.get("id")
        if inline_query_id:
            await send_inline_query_help(inline_query_id)
        return {"status": "ok", "message": "Help results sent"}

    chat_type = _normalize_chat_type(inline_query.get("chat_type"))
    raw_chat_id = payload.get("chat_id")
    inline_message_id = inline_query.get("id")

    placeholder_text = build_inline_placeholder(
        trigger_type=InlineTriggerType.inline_query, chat_type=chat_type
    )

    metadata = {
        "query": inline_query.get("query"),
        "via_bot": inline_query.get("via_bot"),
    }
    consent_scope = "inline_processing"

    if chat_type == InlineChatType.private:
        metadata["privacy_notice"] = True
        metadata["usage_guide_ref"] = "specs/004-add-inline-mode/quickstart.md"
        consent_scope = "inline_private"

    requested_job_id = uuid4()

    try:
        queue_job_id = await enqueue_inline_job(
            job_id=requested_job_id,
            trigger_type=InlineTriggerType.inline_query,
            chat_type=chat_type,
            file_id=file_id,
            raw_chat_id=raw_chat_id,
            raw_user_id=user.get("id"),
            inline_message_id=inline_message_id,
            origin_message_id=payload.get("origin_message_id"),
            thread_id=payload.get("thread_id"),
            consent_scope=consent_scope,
            metadata=metadata,
        )
    except InlineQueueThrottleError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    display_job_id = _resolve_public_job_id(
        requested_job_id=requested_job_id, queue_job_id=str(queue_job_id), seed=file_id
    )

    await send_inline_query_acknowledgement(
        inline_query_id=inline_message_id,
        job_id=display_job_id,
        trigger_type=InlineTriggerType.inline_query,
        placeholder_text=placeholder_text,
    )

    return {
        "status": "ok",
        "job_id": display_job_id,
        "trigger_type": InlineTriggerType.inline_query.value,
    }


async def handle_inline_reply(message: TelegramMessage) -> dict[str, Any]:
    """Handle reply mentions that reference a photo message."""
    reply = message.reply_to_message or {}
    file_id = _best_photo_file_id(reply.get("photo"))
    if not file_id:
        raise HTTPException(status_code=400, detail="Inline reply missing photo")

    chat = message.chat or {}
    raw_chat_id = chat.get("id")
    if not isinstance(raw_chat_id, int):
        raise HTTPException(status_code=400, detail="Inline reply missing valid chat identifier")
    chat_id = raw_chat_id

    reply_message_id = reply.get("message_id")
    if not isinstance(reply_message_id, int):
        raise HTTPException(status_code=400, detail="Inline reply missing message reference")

    requested_job_id = uuid4()

    try:
        queue_job_id = await enqueue_inline_job(
            job_id=requested_job_id,
            trigger_type=InlineTriggerType.reply_mention,
            chat_type=_normalize_chat_type(chat.get("type")),
            file_id=file_id,
            raw_chat_id=chat_id,
            raw_user_id=(message.from_user or {}).get("id"),
            reply_to_message_id=reply_message_id,
            thread_id=message.message_thread_id,
            origin_message_id=str(reply_message_id),
            metadata={
                "reply_author_id": (reply.get("from") or {}).get("id"),
                "media_group_id": reply.get("media_group_id"),
                "chat_title": chat.get("title"),
                "failure_dm_required": True,
            },
        )
    except InlineQueueThrottleError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    display_job_id = _resolve_public_job_id(
        requested_job_id=requested_job_id, queue_job_id=str(queue_job_id), seed=file_id
    )

    await send_group_inline_placeholder(
        chat_id=chat_id,
        thread_id=message.message_thread_id,
        reply_to_message_id=reply_message_id,
        job_id=display_job_id,
        trigger_type=InlineTriggerType.reply_mention,
    )

    logger.info(
        "Inline reply job enqueued",
        extra={
            "job_id": str(queue_job_id),
            "display_job_id": display_job_id,
            "chat_id": chat_id,
            "trigger_type": InlineTriggerType.reply_mention.value,
        },
    )

    return {
        "status": "ok",
        "job_id": display_job_id,
        "trigger_type": InlineTriggerType.reply_mention.value,
    }


async def handle_inline_tagged_photo(message: TelegramMessage) -> dict[str, Any]:
    """Handle tagged photo messages in group chats."""
    file_id = _best_photo_file_id(message.photo)
    if not file_id:
        raise HTTPException(status_code=400, detail="Inline tagged photo missing file reference")

    chat = message.chat or {}
    raw_chat_id = chat.get("id")
    if not isinstance(raw_chat_id, int):
        raise HTTPException(
            status_code=400, detail="Inline tagged photo missing valid chat identifier"
        )
    chat_id = raw_chat_id

    requested_job_id = uuid4()

    try:
        queue_job_id = await enqueue_inline_job(
            job_id=requested_job_id,
            trigger_type=InlineTriggerType.tagged_photo,
            chat_type=_normalize_chat_type(chat.get("type")),
            file_id=file_id,
            raw_chat_id=chat_id,
            raw_user_id=(message.from_user or {}).get("id"),
            reply_to_message_id=message.message_id,
            thread_id=message.message_thread_id,
            origin_message_id=str(message.message_id),
            metadata={
                "caption": message.caption,
                "media_group_id": message.media_group_id,
                "chat_title": chat.get("title"),
                "failure_dm_required": True,
            },
        )
    except InlineQueueThrottleError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    display_job_id = _resolve_public_job_id(
        requested_job_id=requested_job_id, queue_job_id=str(queue_job_id), seed=file_id
    )

    await send_group_inline_placeholder(
        chat_id=chat_id,
        thread_id=message.message_thread_id,
        reply_to_message_id=message.message_id,
        job_id=display_job_id,
        trigger_type=InlineTriggerType.tagged_photo,
    )

    logger.info(
        "Inline tagged photo job enqueued",
        extra={
            "job_id": str(queue_job_id),
            "display_job_id": display_job_id,
            "chat_id": chat_id,
            "trigger_type": InlineTriggerType.tagged_photo.value,
        },
    )

    return {
        "status": "ok",
        "job_id": display_job_id,
        "trigger_type": InlineTriggerType.tagged_photo.value,
    }


def _is_from_telegram(request: Request) -> bool:
    """Check the secret token Telegram sends with every update, when one is configured."""
    if not TELEGRAM_WEBHOOK_SECRET:
        return True
    received = request.headers.get("x-telegram-bot-api-secret-token", "")
    return hmac.compare_digest(received.encode(), TELEGRAM_WEBHOOK_SECRET.encode())


@router.post("/bot")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    if not _is_from_telegram(request):
        logger.warning("Rejected webhook update without a valid secret token")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        # Parse the incoming webhook data
        data = await request.json()
        # Only log full webhook data in debug mode to reduce CPU usage
        logger.debug(f"Received Telegram webhook: {data}")

        if "inline_query" in data:
            return await handle_inline_query(data["inline_query"])

        # Log detailed message info for debugging photo grouping issues (only for photos)
        if data.get("message", {}).get("photo"):
            logger.info(
                f"Photo message details - media_group_id: {data['message'].get('media_group_id')}, message_id: {data['message'].get('message_id')}"
            )

        update = TelegramUpdate(**data)

        if not update.message:
            logger.debug("No message in update, skipping")
            return {"status": "ok"}

        message = TelegramMessage(**update.message)
        logger.info(
            f"Processing message from user {message.from_user.get('id') if message.from_user else 'unknown'}"
        )

        if _is_inline_reply(message):
            return await handle_inline_reply(message)

        if _is_tagged_inline_photo(message):
            return await handle_inline_tagged_photo(message)

        # Handle /start command
        if message.text and message.text.startswith("/start"):
            try:
                await handle_start_command(message)
            except Exception as e:
                logger.error(f"Error handling start command: {e}", exc_info=True)
            return {"status": "ok"}

        # Handle photo messages
        if message.photo:
            try:
                await handle_photo_message(message)
            except Exception as e:
                logger.error(f"Error handling photo message: {e}", exc_info=True)
            return {"status": "ok"}

        # Handle other text messages
        if message.text:
            try:
                await handle_text_message(message)
            except Exception as e:
                logger.error(f"Error handling text message: {e}", exc_info=True)
            return {"status": "ok"}

        logger.info("Unhandled message type received")
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


async def handle_start_command(message: TelegramMessage) -> None:
    """Handle /start command from user."""
    user_id = message.from_user.get("id") if message.from_user else None
    username = message.from_user.get("username") if message.from_user else None
    chat_id = message.chat.get("id") if message.chat else None

    logger.info(f"Handling /start command from user {user_id} (@{username})")

    # Create or get user in database
    if user_id:
        await db_get_or_create_user(
            telegram_id=user_id,
            handle=username,
            locale="en",  # Default locale
        )
        logger.info(f"User {user_id} created/retrieved from database")

    # Send welcome message back to user
    if chat_id and TELEGRAM_BOT_TOKEN:
        try:
            bot = telegram.get_bot()
            welcome_text = (
                "🍎 <b>Welcome to Calorie Track AI!</b>\n\n"
                "I can help you track your calories by analyzing photos of your meals.\n\n"
                "<b>How to use:</b>\n"
                "📸 Send me a photo of your meal\n"
                "🤖 I'll analyze it and estimate the calories\n"
                "📊 Track your daily calorie intake\n\n"
                "Just send me a photo to get started!"
            )
            await bot.send_message(chat_id, welcome_text)
            logger.info(f"Welcome message sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")
    else:
        logger.warning("Cannot send welcome message: missing chat_id or bot token")

    logger.info("Start command processed successfully")


async def handle_photo_message(message: TelegramMessage) -> None:
    """Handle photo messages from user, supporting multi-photo media groups."""
    user_id = message.from_user.get("id") if message.from_user else None
    media_group_id = message.media_group_id

    logger.info(f"Handling photo message from user {user_id}, media_group_id: {media_group_id}")

    if not message.photo:
        logger.warning("Photo message received but no photo data found")
        return

    # Get the highest resolution photo
    photo = max(message.photo, key=lambda x: x.get("file_size", 0))
    file_id = photo.get("file_id")

    if not file_id:
        logger.error("No file_id found in photo message")
        return

    # If this is part of a media group, aggregate photos
    if media_group_id:
        logger.info(f"Photo has media_group_id: {media_group_id}, using Telegram grouping")
        await handle_media_group_photo(message, media_group_id, file_id)
    else:
        # No media_group_id - this might be multiple photos sent separately
        # Use improved time-based grouping with better detection
        logger.info(f"Photo has no media_group_id, using time-based grouping for user {user_id}")

        # Track this message for rapid-fire detection
        if user_id:
            current_time = time.time()
            if user_id not in recent_photo_messages:
                recent_photo_messages[user_id] = []

            # Add current message to tracking
            recent_photo_messages[user_id].append(
                {
                    "message_id": message.message_id,
                    "file_id": file_id,
                    "timestamp": current_time,
                    "message": message,
                }
            )

            # Clean up old messages (older than 5 seconds) - only if list is getting large
            if len(recent_photo_messages[user_id]) > 10:
                recent_photo_messages[user_id] = [
                    msg
                    for msg in recent_photo_messages[user_id]
                    if current_time - msg["timestamp"] < 5.0
                ]

            # Only log if there are multiple messages (potential grouping scenario)
            if len(recent_photo_messages[user_id]) > 1:
                logger.info(
                    f"User {user_id} recent photo messages: {len(recent_photo_messages[user_id])}"
                )

        # Check if this looks like a multi-photo upload based on message timing
        # If messages are very close together (< 1 second), they're likely from the same upload
        await handle_time_based_photo_group(message, file_id, user_id)


async def handle_media_group_photo(
    message: TelegramMessage, media_group_id: str, file_id: str
) -> None:
    """Aggregate photos from media group before processing."""
    user_id = message.from_user.get("id") if message.from_user else None
    chat_id = message.chat.get("id") if message.chat else None

    # Initialize or update media group
    if media_group_id not in media_groups:
        media_groups[media_group_id] = {
            "photos": [],
            "caption": message.caption,
            "message": message,
            "processing_task": None,
        }
        logger.info(f"Created new media group: {media_group_id}")

    # Add photo to group
    media_groups[media_group_id]["photos"].append(file_id)
    photo_count = len(media_groups[media_group_id]["photos"])
    logger.info(f"Added photo to media group {media_group_id}, count: {photo_count}")

    # Check 5-photo limit
    if photo_count > 5:
        logger.warning(f"Media group {media_group_id} exceeds 5-photo limit")

        # Send limit message to user (only once)
        if photo_count == 6 and chat_id:
            try:
                bot = telegram.get_bot()
                limit_message = telegram.get_photo_limit_message()
                await bot.send_message(
                    chat_id,
                    limit_message,
                    reply_to_message_id=message.message_id,
                )
                logger.info(f"Photo limit message sent to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send limit message: {e}")

        # Truncate to 5 photos
        media_groups[media_group_id]["photos"] = media_groups[media_group_id]["photos"][:5]
        return

    # Cancel previous processing task if exists
    if media_groups[media_group_id]["processing_task"]:
        try:
            media_groups[media_group_id]["processing_task"].cancel()
            logger.info(f"Cancelled previous processing task for media group {media_group_id}")
        except Exception as e:
            logger.warning(f"Error cancelling previous media group task: {e}")

    # Schedule processing after 1.5s wait (increased for better media group handling)
    async def process_after_wait():
        try:
            await asyncio.sleep(1.5)  # Increased to 1.5 seconds for better grouping

            # Double-check the group still exists and hasn't been processed
            if media_group_id in media_groups and media_group_id not in processing_groups:
                # Mark as processing to prevent duplicates
                processing_groups.add(media_group_id)

                group_data = media_groups.pop(media_group_id)
                photo_ids_list = group_data["photos"]
                caption = group_data["caption"]
                original_message = group_data["message"]

                logger.info(
                    f"Processing media group {media_group_id} with {len(photo_ids_list)} photos"
                )

                try:
                    await process_photo_group(
                        original_message,
                        photo_ids_list,
                        caption,
                    )
                finally:
                    # Remove from processing set
                    processing_groups.discard(media_group_id)
            else:
                logger.info(
                    f"Media group {media_group_id} no longer exists or already processing, skipping"
                )
        except asyncio.CancelledError:
            logger.info(f"Media group processing task for {media_group_id} was cancelled")
        except Exception as e:
            logger.error(
                f"Error in media group processing for {media_group_id}: {e}", exc_info=True
            )

    # Create and store the processing task
    task = asyncio.create_task(process_after_wait())
    media_groups[media_group_id]["processing_task"] = task


async def handle_time_based_photo_group(
    message: TelegramMessage, file_id: str, user_id: str | None
) -> None:
    """Handle photos without media_group_id using time-based grouping."""
    if not user_id:
        # Fallback to immediate processing if no user_id
        logger.warning("No user_id available, processing photo immediately")
        await process_single_photo(message, file_id)
        return

    current_time = time.time()

    # Initialize or update user photo group
    if user_id not in user_photo_groups:
        user_photo_groups[user_id] = {
            "photos": [],
            "caption": message.caption,
            "message": message,
            "processing_task": None,
            "timestamp": current_time,
            "message_ids": [],
        }
        logger.info(f"Created new time-based photo group for user: {user_id}")
    else:
        # Check if photos are within 3 seconds of each other (more generous grouping)
        time_diff = current_time - user_photo_groups[user_id]["timestamp"]
        if time_diff > 3.0:  # 3 seconds timeout for better grouping
            logger.info(
                f"Time gap {time_diff:.2f}s > 3s, processing previous group for user {user_id}"
            )
            # Process previous group first
            await _process_user_photo_group(user_id)
            # Start new group
            user_photo_groups[user_id] = {
                "photos": [],
                "caption": message.caption,
                "message": message,
                "processing_task": None,
                "timestamp": current_time,
                "message_ids": [],
            }
            logger.info(f"Started new time-based photo group for user: {user_id}")

    # Add photo to group
    user_photo_groups[user_id]["photos"].append(file_id)
    user_photo_groups[user_id]["message_ids"].append(message.message_id)
    user_photo_groups[user_id]["timestamp"] = current_time
    logger.info(
        f"Added photo to user {user_id} group, total photos: {len(user_photo_groups[user_id]['photos'])}, message_ids: {user_photo_groups[user_id]['message_ids']}"
    )

    # Check photo limit (max 5 photos)
    if len(user_photo_groups[user_id]["photos"]) > 5:
        chat_id = message.chat.get("id") if message.chat else None
        if chat_id:
            try:
                bot = telegram.get_bot()
                limit_message = telegram.get_photo_limit_message()
                await bot.send_message(chat_id, limit_message)
            except Exception as e:
                logger.error(f"Failed to send limit message: {e}")

        # Truncate to 5 photos
        user_photo_groups[user_id]["photos"] = user_photo_groups[user_id]["photos"][:5]
        return

    # Cancel previous processing task if exists
    if user_photo_groups[user_id]["processing_task"]:
        try:
            user_photo_groups[user_id]["processing_task"].cancel()
            logger.info(f"Cancelled previous processing task for user {user_id}")
        except Exception as e:
            logger.warning(f"Error cancelling previous task: {e}")

    # Schedule processing after 2.0 second wait (increased for better grouping)
    async def process_after_wait():
        try:
            await asyncio.sleep(2.0)  # 2.0 second wait for time-based grouping

            # Double-check the group still exists and hasn't been processed
            if user_id in user_photo_groups and f"user_{user_id}" not in processing_groups:
                # Mark as processing to prevent duplicates
                processing_groups.add(f"user_{user_id}")

                logger.info(
                    f"Processing delayed group for user {user_id} with {len(user_photo_groups[user_id]['photos'])} photos"
                )

                try:
                    await _process_user_photo_group(user_id)
                finally:
                    # Remove from processing set
                    processing_groups.discard(f"user_{user_id}")
            else:
                logger.info(
                    f"Photo group for user {user_id} no longer exists or already processing, skipping"
                )
        except asyncio.CancelledError:
            logger.info(f"Processing task for user {user_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in delayed processing for user {user_id}: {e}", exc_info=True)

    # Create and store the processing task
    task = asyncio.create_task(process_after_wait())
    user_photo_groups[user_id]["processing_task"] = task
    logger.info(f"Scheduled processing task for user {user_id} in 2.0 seconds")


async def _process_user_photo_group(user_id: str) -> None:
    """Process accumulated photos for a user."""
    if user_id not in user_photo_groups:
        logger.warning(f"No photo group found for user {user_id}")
        return

    group_data = user_photo_groups.pop(user_id)
    photo_ids_list = group_data["photos"]
    caption = group_data["caption"]
    original_message = group_data["message"]

    logger.info(
        f"Processing time-based photo group for user {user_id} with {len(photo_ids_list)} photos"
    )

    try:
        await process_photo_group(
            original_message,
            photo_ids_list,
            caption,
        )
        logger.info(f"Successfully processed photo group for user {user_id}")
    except Exception as e:
        logger.error(f"Error processing photo group for user {user_id}: {e}", exc_info=True)


async def process_single_photo(message: TelegramMessage, file_id: str) -> None:
    """Process a single photo (no media group)."""
    await process_photo_group(message, [file_id], message.caption)


async def keep_sending_status_indicator(
    chat_id: int, stop_event: asyncio.Event, max_duration: float = 120.0
) -> None:
    """Keep sending 'upload_photo' status indicator every 4 seconds until stopped.

    Args:
        chat_id: Target chat ID
        stop_event: Event to signal when to stop sending indicators
        max_duration: Maximum seconds to run before auto-stopping (safety net)
    """
    bot = telegram.get_bot()
    start_time = time.monotonic()
    try:
        while not stop_event.is_set():
            elapsed = time.monotonic() - start_time
            if elapsed >= max_duration:
                logger.warning(
                    f"Status indicator for chat {chat_id} exceeded max duration "
                    f"({max_duration}s), stopping"
                )
                break

            try:
                await bot.send_chat_action(chat_id, "upload_photo")
                logger.debug(f"Sent status indicator to chat {chat_id}")
            except Exception as e:
                logger.warning(f"Failed to send status indicator: {e}")

            # Wait 4 seconds or until stop event is set
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
                break  # Stop event was set
            except TimeoutError:
                continue  # Continue sending indicators
    except asyncio.CancelledError:
        logger.debug(f"Status indicator task cancelled for chat {chat_id}")


async def _process_photo_group_inner(
    message: TelegramMessage,
    file_ids: list[str],
    description: str | None,
    user_id: int | None,
    chat_id: int | None,
) -> None:
    """Inner photo processing logic (download, upload, enqueue)."""
    # Get or create user to get proper UUID
    username = message.from_user.get("username") if message.from_user else None
    user_uuid = None
    if user_id:
        user_uuid = await db_get_or_create_user(
            telegram_id=user_id,
            handle=username,
            locale="en",  # Default locale
        )
        logger.info(f"User {user_id} created/retrieved with UUID: {user_uuid}")

    # Download and upload all photos
    bot = telegram.get_bot()
    photo_ids = []

    for idx, file_id in enumerate(file_ids):
        try:
            # Download photo from Telegram
            file_info = await bot.get_file(file_id)
            file_path = file_info["file_path"]
            logger.info(f"Downloading photo {idx + 1}/{len(file_ids)}: {file_path}")

            photo_content = await bot.download_file(file_path)

            # Get presigned URL for upload
            storage_key, upload_url = await tigris_presign_put(content_type="image/jpeg")
            logger.info(f"Generated presigned URL for storage key: {storage_key}")

            # Upload photo to Tigris
            async with httpx.AsyncClient(timeout=30.0) as client:
                upload_response = await client.put(
                    upload_url,
                    content=photo_content,
                    headers={"Content-Type": "image/jpeg"},
                )
                upload_response.raise_for_status()
            logger.info(f"Photo {idx + 1} uploaded to Tigris")

            # Create photo record in database with display_order
            photo_id = await db_create_photo(
                tigris_key=storage_key,
                user_id=user_uuid,
                display_order=idx,
                media_group_id=message.media_group_id,
            )
            photo_ids.append(photo_id)
            logger.info(f"Photo record created with ID: {photo_id}")

        except Exception as e:
            logger.error(f"Error processing photo {idx + 1}: {e}", exc_info=True)
            # Continue with other photos

    if not photo_ids:
        raise ValueError("No photos were successfully processed")

    # Enqueue estimation job for all photos
    job_id = await enqueue_estimate_job(
        photo_ids, description=description, chat_id=chat_id, telegram_id=user_id
    )
    logger.info(f"Estimation job enqueued for {len(photo_ids)} photo(s), job ID: {job_id}")


# Maximum time (seconds) for photo download/upload/enqueue before giving up
PHOTO_PROCESSING_TIMEOUT = 90.0


async def process_photo_group(
    message: TelegramMessage,
    file_ids: list[str],
    description: str | None,
) -> None:
    """Process one or more photos as a single meal."""
    user_id = message.from_user.get("id") if message.from_user else None
    chat_id = message.chat.get("id") if message.chat else None
    logger.info(f"Processing {len(file_ids)} photo(s) from user {user_id}")

    # Start status indicator task
    stop_indicator = asyncio.Event()
    indicator_task = None
    if chat_id:
        indicator_task = asyncio.create_task(keep_sending_status_indicator(chat_id, stop_indicator))

    try:
        await asyncio.wait_for(
            _process_photo_group_inner(message, file_ids, description, user_id, chat_id),
            timeout=PHOTO_PROCESSING_TIMEOUT,
        )
    except TimeoutError:
        logger.error(
            f"Photo processing timed out after {PHOTO_PROCESSING_TIMEOUT}s "
            f"for user {user_id} ({len(file_ids)} photos)"
        )
        if chat_id and TELEGRAM_BOT_TOKEN:
            try:
                bot = telegram.get_bot()
                await bot.send_message(
                    chat_id,
                    "❌ Sorry, processing your photo(s) took too long. Please try again later.",
                    reply_to_message_id=message.message_id,
                )
            except Exception as e:
                logger.error(f"Failed to send timeout message: {e}")
    except Exception as e:
        logger.error(f"Error processing photo group: {e}", exc_info=True)

        # Send error message to user
        if chat_id and TELEGRAM_BOT_TOKEN:
            try:
                bot = telegram.get_bot()
                await bot.send_message(
                    chat_id,
                    "❌ Sorry, I encountered an error processing your photo(s). Please try again later.",
                    reply_to_message_id=message.message_id,
                )
                logger.info(f"Error message sent to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
    finally:
        # Stop status indicator task
        if indicator_task:
            stop_indicator.set()
            try:
                await asyncio.wait_for(indicator_task, timeout=2.0)
            except TimeoutError:
                indicator_task.cancel()
                try:
                    await indicator_task
                except asyncio.CancelledError:
                    pass
            logger.debug(f"Status indicator task stopped for chat {chat_id}")


async def handle_text_message(message: TelegramMessage) -> None:
    """Handle text messages from user."""
    user_id = message.from_user.get("id") if message.from_user else None
    chat_id = message.chat.get("id") if message.chat else None
    text = message.text or ""

    logger.info(f"Handling text message from user {user_id}: {text[:100]}...")

    # Send helpful response for unknown commands
    if chat_id and TELEGRAM_BOT_TOKEN:
        try:
            bot = telegram.get_bot()
            response_text = (
                "🤖 I'm a calorie tracking bot!\n\n"
                "Here's what I can do:\n"
                "• Send me <b>/start</b> to get started\n"
                "• Send me a <b>photo of your meal</b> to get calorie estimates\n"
                "• I'll analyze your food and tell you the calories\n\n"
                "Try sending me a photo of your meal! 📸"
            )
            await bot.send_message(chat_id, response_text, reply_to_message_id=message.message_id)
            logger.info(f"Help message sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send help message: {e}")

    logger.info(f"Text message processed: {text}")


@router.post("/bot/setup")
async def setup_webhook():
    """Setup Telegram webhook if configured."""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")

    if not USE_WEBHOOK or not WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="Webhook not enabled or URL not configured")

    try:
        bot = telegram.get_bot()
        success = await bot.set_webhook(WEBHOOK_URL, secret_token=TELEGRAM_WEBHOOK_SECRET)

        if success:
            logger.info(f"Webhook set successfully: {WEBHOOK_URL}")
            return {"status": "success", "webhook_url": WEBHOOK_URL}
        else:
            logger.error("Failed to set webhook")
            raise HTTPException(status_code=500, detail="Failed to set webhook")

    except Exception as e:
        logger.error(f"Error setting webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error setting webhook: {e!s}") from e


@router.get("/bot/webhook-info")
async def get_webhook_info():
    """Get current webhook information."""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")

    try:
        bot = telegram.get_bot()
        info = await bot.get_webhook_info()
        return {"status": "success", "webhook_info": info}

    except Exception as e:
        logger.error(f"Error getting webhook info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting webhook info: {e!s}") from e


@router.delete("/bot/webhook")
async def delete_webhook():
    """Delete current webhook."""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")

    try:
        bot = telegram.get_bot()
        success = await bot.delete_webhook()

        if success:
            logger.info("Webhook deleted successfully")
            return {"status": "success", "message": "Webhook deleted"}
        else:
            logger.error("Failed to delete webhook")
            raise HTTPException(status_code=500, detail="Failed to delete webhook")

    except Exception as e:
        logger.error(f"Error deleting webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting webhook: {e!s}") from e
