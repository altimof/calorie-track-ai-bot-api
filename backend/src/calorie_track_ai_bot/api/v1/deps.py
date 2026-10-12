"""Shared FastAPI dependencies for API v1 route handlers.

Provides reusable dependency functions for authentication and user resolution.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request

from ...services import config
from ...services.db import resolve_user_id
from ...services.telegram_auth import InitDataError, validate_init_data

INIT_DATA_SCHEME = "tma "


def get_telegram_user_id(request: Request) -> str:
    """Return the telegram user ID from signed Mini App initData.

    initData is sent as `Authorization: tma <initData>`. If it is absent and
    ALLOW_INSECURE_USER_ID_HEADER is on, the unsigned x-user-id header is used.
    Use as a FastAPI dependency: Depends(get_telegram_user_id)
    """
    authorization = request.headers.get("authorization", "")
    if authorization[: len(INIT_DATA_SCHEME)].lower() == INIT_DATA_SCHEME:
        if not config.TELEGRAM_BOT_TOKEN:
            config.logger.error("Cannot validate initData: TELEGRAM_BOT_TOKEN not configured")
            raise HTTPException(status_code=500, detail="Authentication not configured")
        try:
            user_id = validate_init_data(
                authorization[len(INIT_DATA_SCHEME) :].strip(), config.TELEGRAM_BOT_TOKEN
            )
        except InitDataError as e:
            config.logger.warning(f"Rejected initData: {e}")
            raise HTTPException(status_code=401, detail="Invalid Telegram initData") from e
        return str(user_id)

    if config.ALLOW_INSECURE_USER_ID_HEADER:
        telegram_user_id = request.headers.get("x-user-id")
        if telegram_user_id:
            return telegram_user_id

    raise HTTPException(status_code=401, detail="Missing Telegram initData")


async def get_authenticated_user_id(request: Request) -> str:
    """Authenticate the request and resolve the telegram user to an internal user ID.

    Combines user authentication (x-user-id header extraction) with database
    user ID resolution into a single reusable dependency.
    """
    telegram_user_id = get_telegram_user_id(request)
    internal_user_id = await resolve_user_id(telegram_user_id)
    if not internal_user_id:
        raise HTTPException(status_code=404, detail="User not found")
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
