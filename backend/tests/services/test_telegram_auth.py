"""Tests for Telegram Mini App initData validation."""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from calorie_track_ai_bot.services.telegram_auth import (
    INIT_DATA_MAX_AGE_SECONDS,
    InitDataError,
    validate_init_data,
)

BOT_TOKEN = "123456:TEST-TOKEN"
NOW = 1_760_000_000


def sign(fields: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    """Build initData signed the way Telegram signs it."""
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def make_fields(user_id: object = 59357664, auth_date: int = NOW) -> dict[str, str]:
    return {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps({"id": user_id, "first_name": "Test", "language_code": "en"}),
        "auth_date": str(auth_date),
    }


class TestValidateInitData:
    def test_valid_returns_user_id(self):
        assert validate_init_data(sign(make_fields()), BOT_TOKEN, now=NOW) == 59357664

    def test_field_order_does_not_matter(self):
        fields = make_fields()
        signed = sign(fields)
        reordered = "&".join(reversed(signed.split("&")))
        assert validate_init_data(reordered, BOT_TOKEN, now=NOW) == 59357664

    def test_tampered_user_rejected(self):
        signed = sign(make_fields())
        tampered = signed.replace("59357664", "11111111")
        with pytest.raises(InitDataError, match="signature"):
            validate_init_data(tampered, BOT_TOKEN, now=NOW)

    def test_wrong_bot_token_rejected(self):
        with pytest.raises(InitDataError, match="signature"):
            validate_init_data(sign(make_fields(), "999:OTHER"), BOT_TOKEN, now=NOW)

    def test_expired_rejected(self):
        signed = sign(make_fields(auth_date=NOW - INIT_DATA_MAX_AGE_SECONDS - 1))
        with pytest.raises(InitDataError, match="expired"):
            validate_init_data(signed, BOT_TOKEN, now=NOW)

    def test_at_max_age_accepted(self):
        signed = sign(make_fields(auth_date=NOW - INIT_DATA_MAX_AGE_SECONDS))
        assert validate_init_data(signed, BOT_TOKEN, now=NOW) == 59357664

    def test_non_ascii_hash_rejected(self):
        fields = urlencode(make_fields())
        with pytest.raises(InitDataError, match="signature"):
            validate_init_data(f"{fields}&hash=%C3%A9", BOT_TOKEN, now=NOW)

    def test_missing_hash_rejected(self):
        with pytest.raises(InitDataError, match="no hash"):
            validate_init_data(urlencode(make_fields()), BOT_TOKEN, now=NOW)

    def test_duplicate_field_rejected(self):
        signed = sign(make_fields())
        with pytest.raises(InitDataError, match="Duplicate"):
            validate_init_data(signed + "&auth_date=1", BOT_TOKEN, now=NOW)

    @pytest.mark.parametrize("init_data", ["", "not a query string", "a=1&&b"])
    def test_malformed_rejected(self, init_data):
        with pytest.raises(InitDataError):
            validate_init_data(init_data, BOT_TOKEN, now=NOW)

    def test_missing_bot_token_rejected(self):
        with pytest.raises(InitDataError, match="bot token"):
            validate_init_data(sign(make_fields()), "", now=NOW)

    def test_missing_auth_date_rejected(self):
        fields = make_fields()
        del fields["auth_date"]
        with pytest.raises(InitDataError, match="auth_date"):
            validate_init_data(sign(fields), BOT_TOKEN, now=NOW)

    def test_missing_user_rejected(self):
        fields = make_fields()
        del fields["user"]
        with pytest.raises(InitDataError, match="user"):
            validate_init_data(sign(fields), BOT_TOKEN, now=NOW)

    @pytest.mark.parametrize("user_id", ["59357664", None, True, 1.5])
    def test_non_integer_user_id_rejected(self, user_id):
        with pytest.raises(InitDataError, match="user"):
            validate_init_data(sign(make_fields(user_id=user_id)), BOT_TOKEN, now=NOW)
