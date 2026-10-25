"""Tests for registering the webhook with Telegram."""

from unittest.mock import AsyncMock, Mock

import pytest

from calorie_track_ai_bot.services.telegram import TelegramBot


def _bot_with_mock_client() -> tuple[TelegramBot, AsyncMock]:
    bot = TelegramBot(token="TOKEN")
    response = Mock()
    response.raise_for_status = Mock()
    response.json = Mock(return_value={"ok": True})
    post = AsyncMock(return_value=response)
    bot.client = Mock(post=post)
    return bot, post


@pytest.mark.asyncio
async def test_set_webhook_sends_secret_token():
    bot, post = _bot_with_mock_client()

    assert await bot.set_webhook("https://example.com/bot", secret_token="s3cret")

    assert post.call_args.kwargs["json"] == {
        "url": "https://example.com/bot",
        "secret_token": "s3cret",
    }


@pytest.mark.asyncio
async def test_set_webhook_without_secret_token():
    bot, post = _bot_with_mock_client()

    assert await bot.set_webhook("https://example.com/bot")

    assert post.call_args.kwargs["json"] == {"url": "https://example.com/bot"}
