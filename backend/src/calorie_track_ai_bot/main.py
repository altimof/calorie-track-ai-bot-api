import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .api.v1 import (
    bot,
    config,
    connectivity,
    daily_summary,
    dev,
    estimates,
    feedback,
    goals,
    health,
    inline_analytics,
    logs,
    meals,
    photos,
    statistics,
)
from .services.config import (
    ENABLE_WORKER,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_SECRET,
    USE_WEBHOOK,
    WEBHOOK_URL,
    get_app_env,
    get_cors_origins,
    get_trusted_hosts,
    logger,
)
from .services.database import close_pool
from .services.queue import r as redis_client
from .services.telegram import get_bot

# Initialize structured logger
struct_logger = structlog.get_logger(__name__)


# Middleware functions
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to all requests for distributed tracing."""
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())

    # Bind correlation ID to the logger context
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # Add correlation ID to request state for access in endpoints
    request.state.correlation_id = correlation_id

    response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["x-correlation-id"] = correlation_id

    # Clear context variables
    structlog.contextvars.clear_contextvars()

    return response


# Request headers never written to the logs: they carry credentials
# (Telegram initData, the admin token, Telegram's webhook secret).
REDACTED_HEADERS = {"authorization", "cookie", "x-user-id", "x-telegram-bot-api-secret-token"}


async def request_logging_middleware(request: Request, call_next):
    """Log all requests with structured logging."""
    start_time = time.time()

    # Get correlation ID from request state
    correlation_id = getattr(request.state, "correlation_id", "unknown")

    # Log request start (redact sensitive headers)
    safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in REDACTED_HEADERS}
    struct_logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        headers=safe_headers,
        correlation_id=correlation_id,
    )

    try:
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time

        # Log successful response
        struct_logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time,
            correlation_id=correlation_id,
        )

        # Add timing header
        response.headers["x-process-time"] = str(process_time)

        return response

    except Exception as e:
        # Calculate response time for errors
        process_time = time.time() - start_time

        # Log error
        struct_logger.error(
            "Request failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            error_type=type(e).__name__,
            process_time=process_time,
            correlation_id=correlation_id,
        )

        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    import asyncio

    # Startup
    logger.info("Starting Calories Count API application")

    if USE_WEBHOOK and TELEGRAM_BOT_TOKEN and WEBHOOK_URL:
        logger.info("Setting up Telegram webhook automatically...")
        try:
            bot = get_bot()
            success = await bot.set_webhook(WEBHOOK_URL, secret_token=TELEGRAM_WEBHOOK_SECRET)
            if not TELEGRAM_WEBHOOK_SECRET:
                logger.warning(
                    "TELEGRAM_WEBHOOK_SECRET is not set: webhook updates are not verified"
                )
            if success:
                logger.info(f"✅ Telegram webhook set successfully: {WEBHOOK_URL}")
            else:
                logger.error("❌ Failed to set Telegram webhook")
        except Exception as e:
            logger.error(f"❌ Error setting up Telegram webhook: {e}")
    else:
        logger.info("Telegram webhook setup skipped (not configured)")

    # Start background worker tasks if enabled
    worker_tasks: list[asyncio.Task] = []
    if ENABLE_WORKER:
        from .workers.estimate_worker import process_estimate_jobs, process_inline_jobs

        logger.info("Starting background worker tasks...")
        worker_tasks.append(asyncio.create_task(process_estimate_jobs()))
        worker_tasks.append(asyncio.create_task(process_inline_jobs()))
        logger.info("✅ Background worker tasks started")
    else:
        logger.info("Background worker disabled (ENABLE_WORKER not set)")

    logger.info("All routers registered successfully")

    yield

    # Shutdown - Clean up all resources
    logger.info("Starting application shutdown...")

    # Cancel worker tasks
    for task in worker_tasks:
        task.cancel()
    if worker_tasks:
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        logger.info("✅ Background worker tasks stopped")

    # Close Telegram bot client
    try:
        if TELEGRAM_BOT_TOKEN:
            bot = get_bot()
            await bot.close()
            logger.info("✅ Telegram bot client closed")
        else:
            logger.info("i Telegram bot client cleanup skipped (no token)")
    except Exception as e:
        logger.error(f"❌ Error closing bot client: {e}")

    # Close Redis client
    try:
        if redis_client:
            await redis_client.aclose()
            logger.info("✅ Redis client closed")
        else:
            logger.info("i Redis client cleanup skipped (not configured)")
    except Exception as e:
        logger.error(f"❌ Error closing Redis client: {e}")

    # Close database connection pool
    try:
        await close_pool()
        logger.info("✅ Database connection pool closed")
    except Exception as e:
        logger.error(f"❌ Error closing database pool: {e}")

    logger.info("✅ Application shutdown completed")


app = FastAPI(title="Calories Count API", version="0.1.0", lifespan=lifespan)

# Configure security middleware (Trusted Hosts)
app_env = get_app_env()
if app_env == "production":
    trusted_hosts = get_trusted_hosts()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

# Configure structured logging middleware
app.middleware("http")(request_logging_middleware)

# Configure correlation ID middleware
app.middleware("http")(correlation_id_middleware)

# Configure CORS middleware with environment-specific origins
cors_origins = get_cors_origins()
struct_logger.info(f"Configuring CORS with origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "accept",
        "accept-language",
        "authorization",
        "content-type",
        "x-correlation-id",
        "x-telegram-color-scheme",
        "x-telegram-language-code",
        "x-timezone",
        "x-user-id",
        "sec-ch-prefers-color-scheme",
        "user-agent",
    ],
    expose_headers=[
        "x-correlation-id",
        "x-process-time",
    ],
    max_age=86400,  # 24 hours
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(connectivity.router, prefix="/health", tags=["health"])
app.include_router(config.router, prefix="/api/v1", tags=["configuration"])
app.include_router(logs.router, prefix="/api/v1", tags=["logging"])
app.include_router(dev.router, prefix="/api/v1", tags=["development"])
app.include_router(photos.router, prefix="/api/v1", tags=["photos"])
app.include_router(estimates.router, prefix="/api/v1", tags=["estimates"])
app.include_router(meals.router, prefix="/api/v1", tags=["meals"])
app.include_router(daily_summary.router, prefix="/api/v1", tags=["daily-summary"])
app.include_router(goals.router, prefix="/api/v1", tags=["goals"])
app.include_router(inline_analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
app.include_router(statistics.router, prefix="/api/v1", tags=["statistics"])
app.include_router(bot.router, tags=["bot"])


@app.get("/healthz")
def healthz():
    """Health check endpoint for Fly.io."""
    return {"status": "ok"}
