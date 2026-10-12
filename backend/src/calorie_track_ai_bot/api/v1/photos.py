from fastapi import APIRouter, Depends, HTTPException

from ...schemas import (
    MultiPhotoCreateRequest,
    MultiPhotoResponse,
    PhotoCreateRequest,
    PhotoInfo,
    PresignResponse,
)
from ...services.config import logger
from ...services.db import db_create_photo
from ...services.storage import tigris_presign_put
from .deps import get_authenticated_user_id

router = APIRouter()


@router.post("/photos", response_model=PresignResponse | MultiPhotoResponse)
async def create_photo(
    body: PhotoCreateRequest | MultiPhotoCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
):
    """
    Create photo upload request(s) with support for both single and multi-photo uploads.

    For single photo: Send {"content_type": "image/jpeg"}
    For multiple photos: Send {"photos": [{"content_type": "image/jpeg"}, ...]}
    The photos are owned by the requesting user.
    """

    # Check if this is a multi-photo request using isinstance
    if isinstance(body, MultiPhotoCreateRequest):
        # Multi-photo request
        logger.info(f"Creating {len(body.photos)} photo upload requests")

        successful_photos = []
        failed_photos = []

        for i, photo_request in enumerate(body.photos):
            try:
                key, url = await tigris_presign_put(content_type=photo_request.content_type)
                logger.debug(f"Generated presigned URL for photo {i + 1}: {key}")

                photo_id = await db_create_photo(tigris_key=key, user_id=user_id)
                logger.info(f"Photo {i + 1} record created with ID: {photo_id}")

                successful_photos.append(PhotoInfo(id=photo_id, upload_url=url, file_key=key))

            except Exception as e:
                logger.error(f"Error creating photo {i + 1} upload request: {e}", exc_info=True)
                failed_photos.append({"index": i, "error": str(e)})

        # If all photos failed, return error
        if not successful_photos:
            raise HTTPException(500, f"All photo upload requests failed: {failed_photos}")

        # If some photos failed, log warning but return successful ones
        if failed_photos:
            logger.warning(
                f"Partial upload failure: {len(failed_photos)} photos failed, {len(successful_photos)} succeeded"
            )

        logger.info(f"Successfully created {len(successful_photos)} photo upload requests")
        return MultiPhotoResponse(photos=successful_photos)

    else:
        # Single photo request - body is PhotoCreateRequest
        logger.info(f"Creating photo upload request for content_type: {body.content_type}")
        try:
            key, url = await tigris_presign_put(content_type=body.content_type)
            logger.debug(f"Generated presigned URL for key: {key}")

            photo_id = await db_create_photo(tigris_key=key, user_id=user_id)
            logger.info(f"Photo record created with ID: {photo_id}")

            return PresignResponse(photo_id=photo_id, upload_url=url)
        except Exception as e:
            logger.error(f"Error creating photo upload request: {e}", exc_info=True)
            raise HTTPException(500, str(e)) from e
