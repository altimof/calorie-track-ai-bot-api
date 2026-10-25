"""Admin-only routes require ADMIN_API_TOKEN and are disabled without it."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from calorie_track_ai_bot.main import app

client = TestClient(app)

ADMIN_ROUTES = [
    ("POST", "/bot/setup"),
    ("GET", "/bot/webhook-info"),
    ("DELETE", "/bot/webhook"),
    ("GET", "/api/v1/analytics/inline-summary"),
    ("GET", "/api/v1/dev/environment"),
    ("GET", "/api/v1/dev/db/status"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_disabled_without_admin_token_configured(method, path):
    with patch("calorie_track_ai_bot.services.config.ADMIN_API_TOKEN", None):
        response = client.request(method, path, headers={"Authorization": "Bearer anything"})
    assert response.status_code == 404


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_missing_admin_token_rejected(method, path, admin_headers):
    response = client.request(method, path)
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_wrong_admin_token_rejected(method, path, admin_headers):
    response = client.request(method, path, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_telegram_init_data_is_not_an_admin_token(method, path, admin_headers):
    response = client.request(method, path, headers={"Authorization": "tma user=x&hash=y"})
    assert response.status_code == 401


def test_valid_admin_token_reaches_route(admin_headers):
    bot = Mock(get_webhook_info=AsyncMock(return_value={"url": "https://example.com/bot"}))
    with (
        patch("calorie_track_ai_bot.api.v1.bot.TELEGRAM_BOT_TOKEN", "123:TOKEN"),
        patch("calorie_track_ai_bot.api.v1.bot.telegram.get_bot", return_value=bot),
    ):
        response = client.get("/bot/webhook-info", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["webhook_info"] == {"url": "https://example.com/bot"}


def test_scheme_is_case_insensitive(admin_headers):
    bot = Mock(get_webhook_info=AsyncMock(return_value={}))
    token = admin_headers["Authorization"].split(" ", 1)[1]
    with (
        patch("calorie_track_ai_bot.api.v1.bot.TELEGRAM_BOT_TOKEN", "123:TOKEN"),
        patch("calorie_track_ai_bot.api.v1.bot.telegram.get_bot", return_value=bot),
    ):
        response = client.get("/bot/webhook-info", headers={"Authorization": f"bearer {token}"})

    assert response.status_code == 200
