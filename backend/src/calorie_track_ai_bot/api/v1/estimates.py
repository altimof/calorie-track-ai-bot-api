import uuid

from fastapi import APIRouter, Depends, HTTPException

from ...schemas import EstimateQueuedResponse, EstimateResponse, Status
from ...services.config import logger
from ...services.db import db_get_user_estimate, db_get_user_photo
from ...services.queue import enqueue_estimate_job
from ...utils.error_handling import handle_api_errors
from .deps import get_authenticated_user_id

router = APIRouter()


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


@router.post("/photos/{photo_id}/estimate", response_model=EstimateQueuedResponse)
@handle_api_errors("estimate enqueue")
async def estimate_photo(photo_id: str, user_id: str = Depends(get_authenticated_user_id)):
    # 404 for other users' photos too, so photo IDs can't be probed
    if not _is_uuid(photo_id) or not await db_get_user_photo(photo_id, user_id):
        logger.warning(f"Photo {photo_id} not found for user {user_id}")
        raise HTTPException(404, "Not found")

    logger.info(f"Requesting estimate for photo_id: {photo_id}")
    job_id = await enqueue_estimate_job(photo_id)
    logger.info(f"Estimation job enqueued with ID: {job_id} for photo: {photo_id}")
    return EstimateQueuedResponse(estimate_id=job_id, status=Status.queued)


@router.get("/estimates/{estimate_id}", response_model=EstimateResponse)
@handle_api_errors("estimate retrieval")
async def get_estimate(estimate_id: str, user_id: str = Depends(get_authenticated_user_id)):
    logger.info(f"Fetching estimate with ID: {estimate_id}")
    est = await db_get_user_estimate(estimate_id, user_id) if _is_uuid(estimate_id) else None
    if not est:
        logger.warning(f"Estimate not found for ID: {estimate_id}")
        raise HTTPException(404, "Not found")
    logger.info(f"Estimate retrieved successfully for ID: {estimate_id}")
    return est
