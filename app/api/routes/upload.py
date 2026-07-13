from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.rate_limit import user_rate_limit
from app.schemas.upload import UploadedImageResponse
from app.services.storage_service import upload_post_image

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/post-image",
    response_model=UploadedImageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            user_rate_limit(
                scope="uploads:post-image",
                limit=settings.RATE_LIMIT_UPLOAD_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_UPLOAD_WINDOW_SECONDS,
            )
        )
    ],
)
async def upload_post_image_endpoint(
        current_user: CurrentUser,
        file: Annotated[UploadFile, File(description="Image file for a post")],
) -> UploadedImageResponse:
    return await upload_post_image(user_id=current_user.id, file=file)
