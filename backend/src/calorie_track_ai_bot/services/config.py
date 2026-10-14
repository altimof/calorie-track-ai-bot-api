import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any os.getenv calls
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

APP_ENV: str = os.getenv("APP_ENV", "dev")

# Logging configuration
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Set specific loggers
logger = logging.getLogger("calorie_track_ai_bot")
if LOG_LEVEL == "DEBUG":
    # Enable debug logging for all our modules when DEBUG level is set
    for module_name in ["calorie_track_ai_bot", "fastapi", "uvicorn"]:
        logging.getLogger(module_name).setLevel(logging.DEBUG)

# Suppress DEBUG logs from third-party HTTP libraries that leak secrets (bot tokens, S3 keys)
for module_name in ["httpx", "httpcore", "botocore", "openai"]:
    logging.getLogger(module_name).setLevel(logging.WARNING)

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")

REDIS_URL: str | None = os.getenv("REDIS_URL")

# Tigris S3-compatible storage configuration
# Using standard AWS S3 environment variables as per Fly.io Tigris documentation
AWS_ENDPOINT_URL_S3: str | None = os.getenv("AWS_ENDPOINT_URL_S3")
AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME: str | None = os.getenv("BUCKET_NAME")
AWS_REGION: str = os.getenv("AWS_REGION", "auto")

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")

# Accept the unsigned x-user-id header when no initData is sent. Local development
# and the frontend rollout only: anyone can set this header to any user's ID.
ALLOW_INSECURE_USER_ID_HEADER: bool = (
    os.getenv("ALLOW_INSECURE_USER_ID_HEADER", "false").lower() == "true"
)
if ALLOW_INSECURE_USER_ID_HEADER and APP_ENV == "production":
    logger.warning(
        "ALLOW_INSECURE_USER_ID_HEADER is on in production: the unsigned x-user-id "
        "header is trusted, so any client can act as any user"
    )

# Inline mode configuration
INLINE_MODE_ENABLED: bool = os.getenv("INLINE_MODE_ENABLED", "false").lower() == "true"
INLINE_HASH_SALT: str = os.getenv("INLINE_HASH_SALT", "")
INLINE_THROUGHPUT_PER_MIN: int = int(os.getenv("INLINE_THROUGHPUT_PER_MIN", "60"))
INLINE_BURST_RPS: int = int(os.getenv("INLINE_BURST_RPS", "5"))

# Performance testing configuration
THREAD_DELTA_LIMIT: int = int(os.getenv("THREAD_DELTA_LIMIT", "20"))
PERFORMANCE_THRESHOLD_FACTOR: float = float(os.getenv("PERFORMANCE_THRESHOLD_FACTOR", "1.0"))
HEALTH_TIME_LIMIT: float = float(os.getenv("HEALTH_TIME_LIMIT", "200"))
MEMORY_THRESHOLD_MB: float = float(os.getenv("MEMORY_THRESHOLD_MB", "100"))
CPU_THRESHOLD_PERCENT: float = float(os.getenv("CPU_THRESHOLD_PERCENT", "200"))
WEBHOOK_URL: str | None = os.getenv("WEBHOOK_URL")
USE_WEBHOOK: bool = os.getenv("USE_WEBHOOK", "false").lower() == "true"
ENABLE_WORKER: bool = os.getenv("ENABLE_WORKER", "false").lower() == "true"


# CORS configuration
def get_cors_origins() -> list[str]:
    """Get CORS origins based on environment."""
    cors_origins_env = os.getenv("CORS_ORIGINS", "")

    if cors_origins_env:
        # Parse comma-separated origins from environment variable
        origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
        return origins

    # Default origins based on environment
    if APP_ENV == "production":
        return [
            "https://calorie-track-ai-bot.vercel.app",
            "https://t.me",
        ]
    else:
        # Development environment - allow local development
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "https://localhost:3000",
            "https://127.0.0.1:3000",
        ]


def get_trusted_hosts() -> list[str]:
    """Get trusted hosts for production environment."""
    trusted_hosts_env = os.getenv("TRUSTED_HOSTS", "")

    if trusted_hosts_env:
        return [host.strip() for host in trusted_hosts_env.split(",") if host.strip()]

    # Default trusted hosts for production
    return ["calorie-track-ai-bot.fly.dev", "*.fly.dev", "localhost", "127.0.0.1"]


def get_app_env() -> str:
    """Get application environment."""
    return APP_ENV
