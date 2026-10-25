import asyncio
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException

from ..schemas import InlineTriggerType
from .config import TELEGRAM_BOT_TOKEN, logger


class TelegramBot:
    """Telegram Bot API client for sending messages and managing webhooks."""

    def __init__(self, token: str | None = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        if not self.token:
            raise ValueError("Telegram bot token is required")

        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_to_message_id: int | None = None,
        message_thread_id: int | None = None,
    ) -> dict[str, Any]:
        """Send a text message to a chat."""
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        if message_thread_id is not None:
            data["message_thread_id"] = message_thread_id

        logger.debug(f"Sending message to chat {chat_id}: {text[:100]}...")

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.debug(f"Message sent successfully to chat {chat_id}")
                return result["result"]
            else:
                logger.error(f"Failed to send message: {result.get('description')}")
                raise Exception(f"Telegram API error: {result.get('description')}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending message: {e}")
            raise
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def send_photo(
        self, chat_id: int, photo: str, caption: str | None = None, parse_mode: str = "HTML"
    ) -> dict[str, Any]:
        """Send a photo to a chat."""
        url = f"{self.base_url}/sendPhoto"
        data = {"chat_id": chat_id, "photo": photo}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = parse_mode

        logger.debug(f"Sending photo to chat {chat_id}")

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.info(f"Photo sent successfully to chat {chat_id}")
                return result["result"]
            else:
                logger.error(f"Failed to send photo: {result.get('description')}")
                raise Exception(f"Telegram API error: {result.get('description')}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending photo: {e}")
            raise
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            raise

    async def send_chat_action(self, chat_id: int, action: str) -> bool:
        """Send a chat action (typing, uploading photo, etc.) to a chat.

        Args:
            chat_id: Target chat ID
            action: Action type ('typing', 'upload_photo', 'record_video', etc.)

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/sendChatAction"
        data = {"chat_id": chat_id, "action": action}

        logger.debug(f"Sending chat action '{action}' to chat {chat_id}")

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.debug(f"Chat action sent successfully to chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to send chat action: {result.get('description')}")
                return False

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending chat action: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending chat action: {e}")
            return False

    async def set_webhook(self, webhook_url: str, secret_token: str | None = None) -> bool:
        """Set the webhook URL for the bot.

        With secret_token, Telegram sends it in X-Telegram-Bot-Api-Secret-Token on
        every update, so the webhook can reject requests that don't come from Telegram.
        """
        url = f"{self.base_url}/setWebhook"
        data = {"url": webhook_url}
        if secret_token:
            data["secret_token"] = secret_token

        logger.info(f"Setting webhook URL: {webhook_url}")

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.info("Webhook set successfully")
                return True
            else:
                logger.error(f"Failed to set webhook: {result.get('description')}")
                return False

        except httpx.HTTPError as e:
            logger.error(f"HTTP error setting webhook: {e}")
            return False
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False

    async def get_webhook_info(self) -> dict[str, Any]:
        """Get current webhook information."""
        url = f"{self.base_url}/getWebhookInfo"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                return result["result"]
            else:
                logger.error(f"Failed to get webhook info: {result.get('description')}")
                return {}

        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting webhook info: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error getting webhook info: {e}")
            return {}

    async def delete_webhook(self) -> bool:
        """Delete the current webhook."""
        url = f"{self.base_url}/deleteWebhook"

        logger.info("Deleting webhook")

        try:
            response = await self.client.post(url)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.info("Webhook deleted successfully")
                return True
            else:
                logger.error(f"Failed to delete webhook: {result.get('description')}")
                return False

        except httpx.HTTPError as e:
            logger.error(f"HTTP error deleting webhook: {e}")
            return False
        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            return False

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """Get file information from Telegram."""
        url = f"{self.base_url}/getFile"
        data = {"file_id": file_id}

        logger.debug(f"Getting file info for file_id: {file_id}")

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                logger.info(f"File info retrieved for file_id: {file_id}")
                return result["result"]
            else:
                logger.error(f"Failed to get file info: {result.get('description')}")
                raise Exception(f"Telegram API error: {result.get('description')}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting file info: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            raise

    async def download_file(self, file_path: str) -> bytes:
        """Download file content from Telegram."""
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        logger.debug(f"Downloading file from: {file_url}")

        try:
            response = await self.client.get(file_url)
            response.raise_for_status()

            logger.info(f"File downloaded successfully: {file_path}")
            return response.content

        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def answer_inline_query(
        self,
        inline_query_id: str,
        results: list[dict[str, Any]],
        cache_time: int = 0,
        is_personal: bool = True,
    ) -> dict[str, Any]:
        """Answer an inline query with provided results."""
        url = f"{self.base_url}/answerInlineQuery"
        data = {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
        }

        logger.debug(f"Answering inline query {inline_query_id} with {len(results)} result(s)")

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok", False):
                logger.error(f"Failed to answer inline query: {payload.get('description')}")
                raise Exception(payload.get("description"))
            return payload
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error answering inline query: {exc}")
            raise
        except Exception as exc:
            logger.error(f"Error answering inline query: {exc}")
            raise

    async def edit_message_text(
        self,
        text: str,
        chat_id: int | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        parse_mode: str = "HTML",
    ) -> dict[str, Any]:
        """Edit an existing message or inline placeholder."""
        url = f"{self.base_url}/editMessageText"
        data: dict[str, Any] = {"text": text, "parse_mode": parse_mode}

        if inline_message_id:
            data["inline_message_id"] = inline_message_id
        else:
            if chat_id is None or message_id is None:
                raise ValueError("chat_id and message_id required for chat message editing")
            data["chat_id"] = chat_id
            data["message_id"] = message_id

        logger.debug(
            "Editing message text (inline=%s chat=%s)", inline_message_id or "N/A", chat_id or "N/A"
        )

        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok", False):
                logger.error(f"Failed to edit message: {payload.get('description')}")
                raise Exception(payload.get("description"))
            return payload
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error editing message: {exc}")
            raise
        except Exception as exc:
            logger.error(f"Error editing message: {exc}")
            raise

    async def send_admin_notification(
        self,
        chat_id: int,
        message: str,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any] | None:
        """Send notification to admin chat/channel.

        Feature: 005-mini-app-improvements

        Args:
            chat_id: Telegram chat ID or channel ID (integer)
            message: Notification message text
            parse_mode: Message formatting mode (Markdown, HTML, or None)

        Returns:
            Message response dict if successful, None if failed
        """
        try:
            response = await self.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            logger.info(
                f"Admin notification sent to chat {chat_id}, message length: {len(message)}"
            )
            return response
        except Exception as e:
            logger.error(f"Failed to send admin notification to chat {chat_id}: {e}")
            return None


# Global bot instance
bot: TelegramBot | None = None


def get_bot() -> TelegramBot:
    """Get the global bot instance."""
    global bot
    if bot is None:
        bot = TelegramBot()
    return bot


def _inline_placeholder_text(short_job_id: str) -> str:
    return (
        "🔄 <b>Analyzing meal photo…</b>\n"
        f"Job ID: <code>{short_job_id}</code>\n"
        "We'll share the calorie summary here in a few seconds."
    )


async def send_group_inline_placeholder(
    *,
    chat_id: int,
    thread_id: int | None,
    reply_to_message_id: int | None,
    job_id: str,
    trigger_type: InlineTriggerType,
) -> None:
    """Send a placeholder message back to the group thread while analysis runs."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning(
            "Skipping inline placeholder: Telegram bot token missing",
            extra={"chat_id": chat_id, "thread_id": thread_id, "job_id": job_id},
        )
        return

    bot_instance = get_bot()
    short_job_id = job_id[:8]
    text = _inline_placeholder_text(short_job_id)

    await bot_instance.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=thread_id,
    )
    logger.info(
        "Inline placeholder sent",
        extra={
            "chat_id": chat_id,
            "thread_id": thread_id,
            "job_id": job_id,
            "trigger_type": trigger_type.value,
        },
    )


async def send_inline_query_acknowledgement(
    *,
    inline_query_id: str | None,
    job_id: str,
    trigger_type: InlineTriggerType,
    placeholder_text: str | None = None,
) -> None:
    """Answer inline queries with a placeholder result to keep Telegram UX responsive."""
    if not inline_query_id:
        return

    bot_instance = get_bot()
    short_job_id = job_id[:8]
    message_text = placeholder_text or _inline_placeholder_text(short_job_id)
    placeholder_result = {
        "type": "article",
        "id": job_id,
        "title": "Analyzing meal photo…",
        "description": "Calorie Track AI is working on your photo.",
        "input_message_content": {
            "message_text": message_text,
            "parse_mode": "HTML",
        },
    }

    try:
        await bot_instance.answer_inline_query(
            inline_query_id=inline_query_id,
            results=[placeholder_result],
            cache_time=0,
            is_personal=True,
        )
        logger.info(
            "Inline query acknowledgement sent",
            extra={
                "inline_query_id": inline_query_id,
                "job_id": job_id,
                "trigger_type": trigger_type.value,
            },
        )
    except Exception as exc:
        logger.warning(
            "Failed to answer inline query",
            extra={"inline_query_id": inline_query_id, "error": str(exc)},
        )


async def send_group_inline_result(
    *,
    chat_id: int,
    thread_id: int | None,
    reply_to_message_id: int | None,
    text: str,
) -> None:
    """Send the final inline result back to the originating group conversation."""
    if not TELEGRAM_BOT_TOKEN or os.getenv("PYTEST_CURRENT_TEST"):
        logger.warning(
            "Skipping inline result delivery: Telegram bot token missing",
            extra={"chat_id": chat_id, "thread_id": thread_id},
        )
        return

    bot_instance = get_bot()
    await bot_instance.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=thread_id,
    )
    logger.info(
        "Inline result message sent",
        extra={"chat_id": chat_id, "thread_id": thread_id},
    )


async def send_inline_query_result(*, inline_message_id: str | None, text: str) -> None:
    """Edit inline query result placeholder with the final summary."""
    if not inline_message_id:
        return

    bot_instance = get_bot()
    await bot_instance.edit_message_text(text=text, inline_message_id=inline_message_id)
    logger.info("Inline query result updated", extra={"inline_message_id": inline_message_id})


# Multi-Photo Support Functions (Feature: 003-update-logic-for)


def validate_photo_count(count: int) -> None:
    """Validate photo count is within acceptable range (1-5).

    Args:
        count: Number of photos

    Raises:
        HTTPException: If count is invalid
    """
    if count < 1:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    if count > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 photos allowed per meal. You can upload up to 5 photos in one message for better calorie estimation.",
        )


def get_photo_limit_message() -> str:
    """Get informational message about photo upload limits.

    Returns:
        User-friendly message explaining the 5-photo limit
    """
    return (
        "⚠️ Maximum 5 photos allowed per meal. "
        "You can upload up to 5 photos in one message for better calorie estimation."
    )


def validate_display_order(order: int) -> None:
    """Validate photo display order is within range (0-4).

    Args:
        order: Display order index

    Raises:
        ValueError: If order is out of range
    """
    if order < 0 or order > 4:
        raise ValueError(f"Display order must be between 0 and 4, got {order}")


def validate_photo_mime_type(mime_type: str) -> None:
    """Validate photo has valid image MIME type.

    Args:
        mime_type: MIME type to validate

    Raises:
        ValueError: If MIME type is not a valid image type
    """
    valid_prefixes = ["image/"]
    if not any(mime_type.startswith(prefix) for prefix in valid_prefixes):
        raise ValueError(f"Invalid MIME type: {mime_type}. Must be an image type.")


def validate_photo_file_size(size_bytes: int) -> None:
    """Validate photo file size doesn't exceed Telegram's 20MB limit.

    Args:
        size_bytes: File size in bytes

    Raises:
        ValueError: If file size exceeds limit
    """
    max_size = 20 * 1024 * 1024  # 20MB in bytes
    if size_bytes > max_size:
        raise ValueError(f"Photo size {size_bytes} exceeds 20MB limit")


class TelegramService:
    """Service for handling Telegram message processing including media groups."""

    def __init__(self):
        self._media_group_buffer: dict[str, list[Any]] = {}
        self._media_group_timers: dict[str, datetime] = {}

    async def get_media_group_id(self, update: Any) -> str | None:
        """Extract media_group_id from Telegram update.

        Args:
            update: Telegram update object

        Returns:
            Media group ID if present, None otherwise
        """
        if hasattr(update, "message") and hasattr(update.message, "media_group_id"):
            return update.message.media_group_id
        return None

    async def aggregate_media_group_photos(
        self, media_group_id: str, photo_updates: list[Any], wait_ms: int = 200
    ) -> list[Any]:
        """Aggregate photos from same media group.

        Args:
            media_group_id: Telegram media group identifier
            photo_updates: List of photo update messages
            wait_ms: Maximum wait time in milliseconds

        Returns:
            List of aggregated photos
        """
        # Buffer photos by media_group_id
        if media_group_id not in self._media_group_buffer:
            self._media_group_buffer[media_group_id] = []

        self._media_group_buffer[media_group_id].extend(photo_updates)

        # Wait for completion or timeout
        await asyncio.sleep(wait_ms / 1000.0)

        # Return aggregated photos
        photos = self._media_group_buffer.pop(media_group_id, [])
        self._media_group_timers.pop(media_group_id, None)

        return photos

    async def extract_media_group_caption(self, updates: list[Any]) -> str | None:
        """Extract caption from first photo in media group.

        Args:
            updates: List of photo updates from same media group

        Returns:
            Caption text if present, None otherwise
        """
        for update in updates:
            if hasattr(update, "caption") and update.caption:
                return update.caption
        return None

    async def wait_for_media_group_complete(
        self, media_group_id: str, expected_count: int, timeout_ms: int = 200
    ) -> bool | None:
        """Wait for media group to complete receiving all photos.

        Args:
            media_group_id: Media group identifier
            expected_count: Expected number of photos
            timeout_ms: Maximum wait time in milliseconds

        Returns:
            True if complete, None if timeout
        """
        start_time = datetime.now()

        while True:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            if elapsed_ms >= timeout_ms:
                return None

            # Check if we have all photos
            if media_group_id in self._media_group_buffer:
                if len(self._media_group_buffer[media_group_id]) >= expected_count:
                    return True

            await asyncio.sleep(0.01)  # 10ms polling interval
