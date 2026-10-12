from datetime import UTC, datetime, timedelta

from ..config import logger

# The user's local calendar date of a meal; takes the IANA time zone as its parameter.
LOCAL_MEAL_DATE_SQL = "(created_at AT TIME ZONE %s)::date"

# User ID cache: maps telegram_user_id -> (db_user_id, expiry_time)
_user_id_cache: dict[str, tuple[str, datetime]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes
MAX_CACHE_SIZE = 1000


async def resolve_user_id(telegram_user_id: str | None) -> str | None:
    """Resolve Telegram user ID to database UUID with caching.

    Only looks users up: returns None for a Telegram user who has never used the
    bot. Users are registered by the bot (db_get_or_create_user), not by the API.
    """
    if not telegram_user_id:
        return None

    try:
        current_time = datetime.now(UTC)

        # Clean up expired entries
        expired_keys = [
            key for key, (_, expiry) in _user_id_cache.items() if expiry <= current_time
        ]
        for key in expired_keys:
            _user_id_cache.pop(key, None)
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired user cache entries")

        # Check cache
        if telegram_user_id in _user_id_cache:
            cached_id, expiry = _user_id_cache[telegram_user_id]
            if expiry > current_time:
                logger.debug(f"User ID cache hit for telegram_id: {telegram_user_id}")
                return cached_id
            _user_id_cache.pop(telegram_user_id, None)

        # Lazy import to avoid circular imports
        from .users import db_find_user_id

        telegram_id_int = int(telegram_user_id)
        user_id = await db_find_user_id(telegram_id_int)

        if user_id:
            # Evict oldest entry if cache is full
            if len(_user_id_cache) >= MAX_CACHE_SIZE:
                oldest_key = min(_user_id_cache, key=lambda k: _user_id_cache[k][1])
                _user_id_cache.pop(oldest_key, None)

            _user_id_cache[telegram_user_id] = (
                user_id,
                current_time + timedelta(seconds=CACHE_TTL_SECONDS),
            )
            logger.debug(f"User ID cached for telegram_id: {telegram_user_id}")

        return user_id
    except (ValueError, TypeError):
        logger.warning(f"Invalid telegram_user_id format: {telegram_user_id}")
        return None
