"""Logging endpoint for structured log collection from the frontend."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request

from ...schemas import LogEntryCreate, LogLevel
from ...utils.error_handling import handle_api_errors
from .deps import get_verified_telegram_user_id

router = APIRouter()

logger = structlog.get_logger(__name__)

# Log level to logger method mapping
LOG_LEVEL_METHODS = {
    LogLevel.DEBUG: logger.debug,
    LogLevel.INFO: logger.info,
    LogLevel.WARNING: logger.warning,
    LogLevel.ERROR: logger.error,
    LogLevel.CRITICAL: logger.critical,
}

# Sensitive fields that should be redacted from logs
SENSITIVE_FIELDS = {
    "password",
    "token",
    "secret",
    "key",
    "auth",
    "credential",
    "ssn",
    "social_security",
    "credit_card",
    "email",
    "phone",
    "api_key",
    "access_token",
    "refresh_token",
    "session_id",
}


def _sanitize_context(context: dict[str, Any]) -> dict[str, Any]:
    """Sanitize context data by redacting sensitive information."""
    if not context:
        return {}

    sanitized = {}
    for key, value in context.items():
        key_lower = key.lower()
        is_sensitive = any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS)

        if is_sensitive:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_context(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_context(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


@router.post("/logs", status_code=200)
@handle_api_errors("create_log_entry")
async def create_log_entry(
    log_data: LogEntryCreate,
    request: Request,
    user_id: str = Depends(get_verified_telegram_user_id),
) -> dict[str, str]:
    """Accept a frontend log entry and forward it to structlog."""
    sanitized_context = _sanitize_context(log_data.context) if log_data.context else {}

    log_context: dict[str, Any] = {
        "user_id": user_id,
        "correlation_id": request.state.correlation_id,
        "module": log_data.module,
        "function": log_data.function,
    }
    if sanitized_context:
        log_context.update(sanitized_context)

    log_method = LOG_LEVEL_METHODS.get(log_data.level, logger.info)
    log_method(log_data.message, **log_context)

    return {"status": "ok"}
