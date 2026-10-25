"""Health connectivity endpoint for frontend-backend integration."""

import time
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Request

from ...schemas import ConnectionStatus, ConnectivityResponse
from ...services.config import APP_ENV
from ...utils.error_handling import handle_api_errors
from ...utils.ids import parse_uuid

router = APIRouter()

logger = structlog.get_logger(__name__)

API_VERSION = "1.0.0"


async def _perform_health_checks() -> tuple[bool, dict]:
    """Perform health checks including a real database ping."""
    checks = {}
    is_healthy = True

    try:
        from ...services import database

        if database._pool is not None:
            db_start = time.perf_counter()
            async with database._pool.connection() as conn:
                cur = await conn.execute("SELECT 1")
                await cur.fetchone()
            db_time_ms = (time.perf_counter() - db_start) * 1000
            checks["database"] = {"status": "available", "response_time_ms": round(db_time_ms, 2)}
        else:
            checks["database"] = {"status": "not_initialized"}
    except Exception:
        checks["database"] = {"status": "unavailable"}

    checks["application"] = {"status": "healthy"}

    return is_healthy, checks


@router.get("/connectivity", response_model=ConnectivityResponse)
@handle_api_errors("get_connectivity_status")
async def get_connectivity_status(request: Request) -> ConnectivityResponse:
    """Check connectivity between frontend and backend."""
    start_time = time.perf_counter()

    correlation_id_str = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    correlation_id = parse_uuid(correlation_id_str) or uuid.uuid4()

    is_healthy, check_details = await _perform_health_checks()

    response_time_ms = (time.perf_counter() - start_time) * 1000
    status = ConnectionStatus.connected if is_healthy else ConnectionStatus.error

    response = ConnectivityResponse(
        status=status,
        services={
            "api_version": API_VERSION,
            "environment": APP_ENV,
            "checks_performed": list(check_details.keys()),
            "health_details": check_details,
        },
        response_time_ms=response_time_ms,
        correlation_id=correlation_id,
        timestamp=datetime.now(UTC),
    )

    if not is_healthy:
        raise HTTPException(status_code=503, detail=response.model_dump(mode="json"))

    return response
