"""Development environment endpoints for local development tools and status."""

import os
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from ...schemas import DevelopmentEnvironment
from ...services.config import APP_ENV
from ...utils.error_handling import handle_api_errors
from .admin_auth import require_admin_token

router = APIRouter()

logger = structlog.get_logger(__name__)

DEV_ENDPOINTS_ENABLED = os.getenv("DEV_ENDPOINTS_ENABLED", "true").lower() == "true"

DEVELOPMENT_CONFIG = {
    "database_url": os.getenv("DATABASE_URL", "postgresql://localhost:5432/neondb"),
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
    "storage_endpoint": os.getenv("STORAGE_ENDPOINT", "http://localhost:9000"),
    "frontend_port": int(os.getenv("FRONTEND_PORT", "5173")),
    "backend_port": int(os.getenv("BACKEND_PORT", "8000")),
}

STABLE_ENVIRONMENT_ID = "12345678-1234-5678-9abc-123456789abc"


def _check_dev_endpoints_access() -> bool:
    if APP_ENV == "production" and not DEV_ENDPOINTS_ENABLED:
        logger.warning("Development endpoints access attempted in production")
        return False
    return True


@router.get(
    "/dev/environment",
    response_model=DevelopmentEnvironment,
    dependencies=[Depends(require_admin_token)],
)
@handle_api_errors("get_development_environment")
async def get_development_environment(
    request: Request,
) -> DevelopmentEnvironment:
    """Get current development environment configuration."""
    correlation_id = request.state.correlation_id

    if not _check_dev_endpoints_access():
        raise HTTPException(
            status_code=403,
            detail={
                "error": "access_denied",
                "message": "Development endpoints are not available",
                "correlation_id": correlation_id,
            },
        )

    now = datetime.now(UTC)

    return DevelopmentEnvironment(
        id=uuid.UUID(STABLE_ENVIRONMENT_ID),
        name=f"{APP_ENV}-development" if APP_ENV != "production" else "production-limited",
        frontend_port=DEVELOPMENT_CONFIG["frontend_port"],
        backend_port=DEVELOPMENT_CONFIG["backend_port"],
        database_url=DEVELOPMENT_CONFIG["database_url"],
        database_password="",
        redis_url=DEVELOPMENT_CONFIG["redis_url"],
        storage_endpoint=DEVELOPMENT_CONFIG["storage_endpoint"],
        cors_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
        if APP_ENV != "production"
        else [],
        log_level="DEBUG" if APP_ENV != "production" else "INFO",
        hot_reload=APP_ENV != "production",
        created_at=now,
        updated_at=now,
    )


@router.get("/dev/db/status", dependencies=[Depends(require_admin_token)])
@handle_api_errors("get_db_status")
async def get_db_status(request: Request) -> dict:
    """Get database connection pool status."""
    correlation_id = request.state.correlation_id

    if not _check_dev_endpoints_access():
        raise HTTPException(
            status_code=403,
            detail={"error": "access_denied", "correlation_id": correlation_id},
        )

    from ...services.database import get_pool

    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT 1")
        await cur.fetchone()

    return {
        "status": "running",
        "database_url": DEVELOPMENT_CONFIG["database_url"],
        "last_check": datetime.now(UTC).isoformat(),
    }
