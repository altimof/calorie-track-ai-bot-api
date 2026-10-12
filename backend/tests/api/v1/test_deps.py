"""Tests for Telegram initData authentication and the registered-user check."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from calorie_track_ai_bot.api.v1.deps import get_telegram_user_id
from calorie_track_ai_bot.services import config

BOT_TOKEN = "123456:TEST-TOKEN"

app = FastAPI()


@app.get("/whoami")
async def whoami(telegram_user_id: str = Depends(get_telegram_user_id)):
    return {"telegram_user_id": telegram_user_id}


client = TestClient(app)


def signed_init_data(user_id: int = 59357664, bot_token: str = BOT_TOKEN) -> str:
    fields = {
        "user": json.dumps({"id": user_id, "first_name": "Test"}),
        "auth_date": str(int(time.time())),
    }
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


@pytest.fixture
def secure(monkeypatch):
    """Production settings: bot token set, unsigned header not allowed."""
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setattr(config, "ALLOW_INSECURE_USER_ID_HEADER", False)


@pytest.mark.usefixtures("secure")
class TestInitDataAuth:
    def test_valid_init_data_returns_user_id(self):
        response = client.get("/whoami", headers={"authorization": f"tma {signed_init_data()}"})
        assert response.status_code == 200
        assert response.json() == {"telegram_user_id": "59357664"}

    def test_scheme_is_case_insensitive(self):
        response = client.get("/whoami", headers={"authorization": f"TMA {signed_init_data()}"})
        assert response.status_code == 200

    def test_init_data_wins_over_x_user_id(self):
        response = client.get(
            "/whoami",
            headers={"authorization": f"tma {signed_init_data()}", "x-user-id": "11111111"},
        )
        assert response.json() == {"telegram_user_id": "59357664"}

    def test_invalid_init_data_returns_401(self):
        response = client.get(
            "/whoami",
            headers={"authorization": f"tma {signed_init_data(bot_token='999:OTHER')}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid Telegram initData"

    def test_x_user_id_rejected_when_flag_off(self):
        response = client.get("/whoami", headers={"x-user-id": "59357664"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing Telegram initData"

    def test_other_authorization_scheme_rejected(self):
        response = client.get("/whoami", headers={"authorization": "Bearer abc"})
        assert response.status_code == 401

    def test_missing_bot_token_returns_500(self, monkeypatch):
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", None)
        response = client.get("/whoami", headers={"authorization": f"tma {signed_init_data()}"})
        assert response.status_code == 500


@pytest.mark.usefixtures("secure")
class TestInsecureHeaderFlag:
    def test_x_user_id_accepted_when_flag_on(self, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_INSECURE_USER_ID_HEADER", True)
        response = client.get("/whoami", headers={"x-user-id": "59357664"})
        assert response.status_code == 200
        assert response.json() == {"telegram_user_id": "59357664"}

    def test_invalid_init_data_not_rescued_by_flag(self, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_INSECURE_USER_ID_HEADER", True)
        response = client.get(
            "/whoami",
            headers={"authorization": "tma user=x&hash=bad", "x-user-id": "59357664"},
        )
        assert response.status_code == 401


@pytest.mark.usefixtures("secure")
class TestRegisteredUsersOnly:
    def test_registered_user_is_resolved_by_telegram_id(self, registered_user):
        response = client.get("/whoami", headers={"authorization": f"tma {signed_init_data()}"})
        assert response.status_code == 200
        registered_user.assert_awaited_once_with("59357664")

    def test_unregistered_user_with_valid_init_data_gets_403(self, registered_user):
        registered_user.return_value = None
        response = client.get("/whoami", headers={"authorization": f"tma {signed_init_data()}"})
        assert response.status_code == 403
        assert response.json()["detail"] == "User not registered"

    def test_unregistered_user_via_insecure_header_gets_403(self, registered_user, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_INSECURE_USER_ID_HEADER", True)
        registered_user.return_value = None
        response = client.get("/whoami", headers={"x-user-id": "59357664"})
        assert response.status_code == 403


class TestResolveUserIdLookupOnly:
    @pytest.mark.asyncio
    async def test_unknown_telegram_user_is_not_created(self):
        from calorie_track_ai_bot.services.db import _base

        _base._user_id_cache.clear()
        with (
            patch(
                "calorie_track_ai_bot.services.db.users.db_find_user_id",
                AsyncMock(return_value=None),
            ) as find,
            patch("calorie_track_ai_bot.services.db.users.db_get_or_create_user") as create,
        ):
            assert await _base.resolve_user_id("59357664") is None
        find.assert_awaited_once_with(59357664)
        create.assert_not_called()
        assert "59357664" not in _base._user_id_cache

    @pytest.mark.asyncio
    async def test_registered_telegram_user_is_cached(self):
        from calorie_track_ai_bot.services.db import _base

        _base._user_id_cache.clear()
        user_uuid = "1d882190-ac3f-4a06-8a44-20e46bafb9a5"
        with patch(
            "calorie_track_ai_bot.services.db.users.db_find_user_id",
            AsyncMock(return_value=user_uuid),
        ) as find:
            assert await _base.resolve_user_id("59357664") == user_uuid
            assert await _base.resolve_user_id("59357664") == user_uuid
        find.assert_awaited_once()
        _base._user_id_cache.clear()
