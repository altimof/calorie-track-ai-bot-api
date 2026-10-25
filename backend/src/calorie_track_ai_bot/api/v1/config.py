"""Configuration management endpoints for UI and system settings."""

import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ...schemas import (
    Environment,
    LanguageDetectionResponse,
    LanguageSource,
    Theme,
    ThemeDetectionResponse,
    ThemeSource,
    UIConfiguration,
    UIConfigurationUpdate,
)
from ...services.config import APP_ENV
from ...services.db import (
    db_create_ui_configuration,
    db_get_ui_configuration,
    db_update_ui_configuration,
)
from ...utils.error_handling import handle_api_errors
from .deps import get_telegram_user_id, get_verified_telegram_user_id

router = APIRouter()

logger = structlog.get_logger(__name__)

# Allowed feature flags with validation
ALLOWED_FEATURE_FLAGS = {
    "enableThemeDetection": bool,
    "enableLanguageDetection": bool,
    "enableSafeAreas": bool,
    "enableLogging": bool,
    "enableDebugLogging": bool,
    "enableErrorReporting": bool,
    "enableAnalytics": bool,
    "enablePerformanceMonitoring": bool,
}

# ISO 639-1 language codes for validation
ISO_639_1_CODES = {"en", "ru"}


def _validate_url(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _validate_language_code(language: str) -> bool:
    """Validate language code against ISO 639-1 standard."""
    if not language or not isinstance(language, str):
        return False
    primary_language = language.split("-")[0].lower()
    return primary_language in ISO_639_1_CODES


def _sanitize_feature_flags(features: dict | None) -> dict:
    """Sanitize and validate feature flags, removing unknown flags."""
    if not features:
        return {}

    sanitized = {}
    for key, value in features.items():
        if key in ALLOWED_FEATURE_FLAGS:
            expected_type = ALLOWED_FEATURE_FLAGS[key]
            if isinstance(value, expected_type):
                sanitized[key] = value
            elif expected_type is bool:
                sanitized[key] = bool(value)

    return sanitized


def _get_environment() -> Environment:
    return Environment.production if APP_ENV == "production" else Environment.development


def _get_api_base_url() -> str:
    if APP_ENV == "production":
        return "https://calorie-track-ai-bot.fly.dev"
    return "http://localhost:8000"


def _default_config() -> UIConfiguration:
    """Create a default UIConfiguration."""
    now = datetime.now(UTC)
    return UIConfiguration(
        id=uuid.uuid4(),
        environment=_get_environment(),
        api_base_url=_get_api_base_url(),
        safe_area_top=44,
        safe_area_bottom=34,
        safe_area_left=0,
        safe_area_right=0,
        theme=Theme.auto,
        theme_source=ThemeSource.telegram,
        language="en",
        language_source=LanguageSource.telegram,
        features={
            "enableThemeDetection": True,
            "enableLanguageDetection": True,
            "enableSafeAreas": True,
            "enableLogging": True,
        },
        created_at=now,
        updated_at=now,
    )


@router.get("/config/ui", response_model=UIConfiguration)
@handle_api_errors("get_ui_configuration")
async def get_ui_configuration(
    request: Request, user_id: str = Depends(get_telegram_user_id)
) -> UIConfiguration:
    """Get current UI configuration for the user."""
    correlation_id = request.state.correlation_id
    logger.info("UI configuration requested", user_id=user_id, correlation_id=correlation_id)

    row = await db_get_ui_configuration(user_id)
    if row:
        return UIConfiguration(**row)

    config = _default_config()
    await db_create_ui_configuration(user_id, config)
    logger.info(
        "Created default UI configuration", config_id=str(config.id), correlation_id=correlation_id
    )
    return config


@router.put("/config/ui", response_model=UIConfiguration)
@handle_api_errors("update_ui_configuration")
async def update_ui_configuration(
    update_data: UIConfigurationUpdate,
    request: Request,
    user_id: str = Depends(get_telegram_user_id),
) -> UIConfiguration:
    """Update UI configuration settings (idempotent)."""
    correlation_id = request.state.correlation_id

    logger.info(
        "UI configuration update requested",
        user_id=user_id,
        correlation_id=correlation_id,
        update_fields=list(update_data.model_dump(exclude_unset=True).keys()),
    )

    validation_errors = {}

    if update_data.api_base_url and not _validate_url(update_data.api_base_url):
        validation_errors["api_base_url"] = "Invalid URL format"

    for field in ["safe_area_top", "safe_area_bottom", "safe_area_left", "safe_area_right"]:
        value = getattr(update_data, field)
        if value is not None and (value < 0 or value > 200):
            validation_errors[field] = "Safe area value must be between 0 and 200 pixels"

    if update_data.language and not _validate_language_code(update_data.language):
        validation_errors["language"] = (
            f"Invalid language code: {update_data.language}. Must be ISO 639-1 format."
        )

    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "Invalid configuration data",
                "validation_errors": validation_errors,
                "correlation_id": correlation_id,
            },
        )

    sanitized_features = _sanitize_feature_flags(update_data.features)
    if update_data.features and sanitized_features != update_data.features:
        logger.info(
            "Feature flags sanitized",
            original_count=len(update_data.features),
            sanitized_count=len(sanitized_features),
        )

    existing_row = await db_get_ui_configuration(user_id)

    if existing_row:
        existing_config = UIConfiguration(**existing_row)
        updated_row = await db_update_ui_configuration(
            user_id, str(existing_config.id), update_data
        )
        if updated_row:
            return UIConfiguration(**updated_row)
        # Fallback: return existing with updates applied locally
        now = datetime.now(UTC)
        updated_config = existing_config.model_copy(
            update={
                k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None
            }
            | {"updated_at": now}
        )
        return updated_config

    # No existing config — create one with updates applied
    config = _default_config()
    update_dict = update_data.model_dump(exclude_unset=True)
    config = config.model_copy(update={k: v for k, v in update_dict.items() if v is not None})
    await db_create_ui_configuration(user_id, config)
    return config


@router.patch("/config/ui", response_model=UIConfiguration)
@handle_api_errors("patch_ui_configuration")
async def patch_ui_configuration(
    update_data: UIConfigurationUpdate,
    request: Request,
    user_id: str = Depends(get_telegram_user_id),
) -> UIConfiguration:
    """Partially update UI configuration settings."""
    correlation_id = request.state.correlation_id

    existing_row = await db_get_ui_configuration(user_id)
    if not existing_row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "config_not_found",
                "message": "UI configuration not found. Use PUT to create initial configuration.",
                "correlation_id": correlation_id,
            },
        )

    return await update_ui_configuration(update_data, request, user_id)


@router.get("/config/theme", response_model=ThemeDetectionResponse)
@handle_api_errors("detect_theme")
async def detect_theme(
    request: Request, user_id: str = Depends(get_verified_telegram_user_id)
) -> ThemeDetectionResponse:
    """Detect and return current theme settings based on context."""
    telegram_color_scheme = request.headers.get("x-telegram-color-scheme")

    user_agent = request.headers.get("user-agent", "").lower()
    system_prefers_dark = (
        "dark" in user_agent or request.headers.get("sec-ch-prefers-color-scheme") == "dark"
    )

    detected_theme = Theme.light
    theme_source = ThemeSource.system

    if telegram_color_scheme:
        detected_theme = Theme.dark if telegram_color_scheme == "dark" else Theme.light
        theme_source = ThemeSource.telegram
    elif system_prefers_dark is not None:
        detected_theme = Theme.dark if system_prefers_dark else Theme.light
        theme_source = ThemeSource.system
    else:
        detected_theme = Theme.auto
        theme_source = ThemeSource.manual

    return ThemeDetectionResponse(
        theme=detected_theme,
        theme_source=theme_source,
        telegram_color_scheme=telegram_color_scheme,
        system_prefers_dark=system_prefers_dark,
        detected_at=datetime.now(UTC),
    )


@router.get("/config/language", response_model=LanguageDetectionResponse)
@handle_api_errors("detect_language")
async def detect_language(
    request: Request, user_id: str = Depends(get_verified_telegram_user_id)
) -> LanguageDetectionResponse:
    """Detect and return current language settings based on context."""
    telegram_language_code = request.headers.get("x-telegram-language-code")

    accept_language = request.headers.get("accept-language", "")
    browser_language = None
    if accept_language:
        languages = accept_language.split(",")
        if languages:
            primary_language = languages[0].strip().split(";")[0]
            browser_language = primary_language

    supported_languages = ["en", "ru"]
    detected_language = "en"
    language_source = LanguageSource.manual

    if telegram_language_code:
        detected_language = telegram_language_code
        language_source = LanguageSource.telegram
    elif browser_language:
        detected_language = browser_language.split("-")[0]
        language_source = LanguageSource.browser

    if (
        not detected_language.isalpha()
        or len(detected_language) < 2
        or detected_language not in supported_languages
    ):
        detected_language = "en"
        language_source = LanguageSource.manual

    return LanguageDetectionResponse(
        language=detected_language,
        language_source=language_source,
        telegram_language_code=telegram_language_code,
        browser_language=browser_language,
        detected_at=datetime.now(UTC),
        supported_languages=supported_languages,
    )
