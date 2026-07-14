from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.rate_limit import user_rate_limit
from app.schemas.user import UserResponse
from app.services.storage_service import upload_profile_image
from app.services.user_service import update_user_profile_image

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/me/profile-image",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            user_rate_limit(
                scope="uploads:profile-image",
                limit=settings.RATE_LIMIT_UPLOAD_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_UPLOAD_WINDOW_SECONDS,
            )
        )
    ],
)
async def upload_my_profile_image_endpoint(
        db: DBSession,
        current_user: CurrentUser,
        file: Annotated[UploadFile, File(description="Profile image file")],
) -> UserResponse:
    uploaded = await upload_profile_image(
        user_id=current_user.id,
        file=file,
    )

    return await update_user_profile_image(
        db=db,
        user=current_user,
        profile_image_url=uploaded.url,
    )
