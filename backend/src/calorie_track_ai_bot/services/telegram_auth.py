"""Validation of Telegram Mini App initData.

See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

# Telegram re-signs initData each time the Mini App is opened
INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60


class InitDataError(ValueError):
    """initData is malformed, has a bad signature, or is expired."""


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = INIT_DATA_MAX_AGE_SECONDS,
    now: float | None = None,
) -> int:
    """Verify Mini App initData and return the Telegram user ID it was signed for.

    Raises InitDataError if the data cannot be trusted.
    """
    if not init_data or not bot_token:
        raise InitDataError("Missing initData or bot token")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as e:
        raise InitDataError("Malformed initData") from e

    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InitDataError("Duplicate initData fields")

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InitDataError("initData has no hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("initData signature mismatch")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError) as e:
        raise InitDataError("initData has no valid auth_date") from e
    if (now if now is not None else time.time()) - auth_date > max_age_seconds:
        raise InitDataError("initData expired")

    try:
        user_id = json.loads(fields["user"])["id"]
    except (KeyError, ValueError, TypeError) as e:
        raise InitDataError("initData has no valid user") from e
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        raise InitDataError("initData has no valid user")
    return user_id
