"""Shared FastAPI dependencies for API v1 route handlers.

Provides reusable dependency functions for authentication and user resolution.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request
from fastapi.security.utils import get_authorization_scheme_param

from ...services import config
from ...services.db import resolve_user_id
from ...services.telegram_auth import InitDataError, validate_init_data


def _identify_telegram_user(request: Request) -> str:
    """Return the telegram user ID from signed Mini App initData.

    initData is sent as `Authorization: tma <initData>`. If it is absent and
    ALLOW_INSECURE_USER_ID_HEADER is on, the unsigned x-user-id header is used.
    """
    scheme, init_data = get_authorization_scheme_param(request.headers.get("authorization"))
    if scheme.lower() == "tma":
        if not config.TELEGRAM_BOT_TOKEN:
            config.logger.error("Cannot validate initData: TELEGRAM_BOT_TOKEN not configured")
            raise HTTPException(status_code=500, detail="Authentication not configured")
        try:
            user_id = validate_init_data(init_data, config.TELEGRAM_BOT_TOKEN)
        except InitDataError as e:
            config.logger.warning(f"Rejected initData: {e}")
            raise HTTPException(status_code=401, detail="Invalid Telegram initData") from e
        return str(user_id)

    if config.ALLOW_INSECURE_USER_ID_HEADER:
        telegram_user_id = request.headers.get("x-user-id")
        if telegram_user_id:
            return telegram_user_id

    raise HTTPException(status_code=401, detail="Missing Telegram initData")


async def _authenticate(request: Request) -> tuple[str, str]:
    """Return (telegram user ID, internal user ID) for a registered user.

    Raises 403 for a Telegram user who is not in the users table: the API serves
    only users registered through the bot.
    """
    telegram_user_id = _identify_telegram_user(request)
    internal_user_id = await resolve_user_id(telegram_user_id)
    if not internal_user_id:
        config.logger.warning(f"Rejected request from unregistered user {telegram_user_id}")
        raise HTTPException(status_code=403, detail="User not registered")
    return telegram_user_id, internal_user_id


def get_verified_telegram_user_id(request: Request) -> str:
    """Return the telegram user ID from verified initData, without the registered-user check.

    For routes that read no user data from the database (logs, theme and language
    detection, dev diagnostics): they need no DB lookup, so they keep working while
    the database is down, and they accept users who have not started the bot yet.
    """
    return _identify_telegram_user(request)


async def get_telegram_user_id(request: Request) -> str:
    """Return the telegram user ID of the registered user making the request.

    Use as a FastAPI dependency: Depends(get_telegram_user_id)
    """
    telegram_user_id, _ = await _authenticate(request)
    return telegram_user_id


async def get_authenticated_user_id(request: Request) -> str:
    """Return the internal user ID of the registered user making the request.

    Use as a FastAPI dependency, or await it directly with the request.
    """
    _, internal_user_id = await _authenticate(request)
    return internal_user_id


def get_user_timezone(request: Request) -> str:
    """Return the client's IANA time zone from the x-timezone header.

    Meals are bucketed into the user's local calendar days with it. Falls back to
    UTC when the header is missing or names an unknown zone.
    Use as a FastAPI dependency: Depends(get_user_timezone)
    """
    tz_name = (request.headers.get("x-timezone") or "").strip()
    if not tz_name:
        return "UTC"
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return "UTC"
    return tz_name
