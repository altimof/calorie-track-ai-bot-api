"""The request log never contains credential headers."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from calorie_track_ai_bot.main import app

client = TestClient(app)


def test_credential_headers_are_not_logged():
    with patch("calorie_track_ai_bot.main.struct_logger") as struct_logger:
        client.get(
            "/health/live",
            headers={
                "Authorization": "tma secret-init-data",
                "Cookie": "session=secret-cookie",
                "X-User-Id": "123456789",
                "X-Telegram-Bot-Api-Secret-Token": "secret-webhook-token",
                "X-Correlation-ID": "kept",
            },
        )

    started = next(
        call for call in struct_logger.info.call_args_list if call.args[0] == "Request started"
    )
    logged = {k.lower(): v for k, v in started.kwargs["headers"].items()}
    assert "authorization" not in logged
    assert "cookie" not in logged
    assert "x-user-id" not in logged
    assert "x-telegram-bot-api-secret-token" not in logged
    assert logged["x-correlation-id"] == "kept"
    assert "secret" not in str(started)
