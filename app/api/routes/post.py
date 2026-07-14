from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.rate_limit import user_rate_limit
from app.models import PostVisibility
from app.schemas.post import PostCreate, PostFeedPage, PostResponse
from app.services.post_service import (
    create_post,
    create_post_with_optional_content,
    list_feed_posts,
)
from app.services.storage_service import upload_post_image

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            user_rate_limit(
                scope="posts:create",
                limit=settings.RATE_LIMIT_POST_WRITE_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_POST_WRITE_WINDOW_SECONDS,
            )
        )
    ],
)
async def create_post_endpoint(
        post_in: PostCreate,
        db: DBSession,
        current_user: CurrentUser,
) -> PostResponse:
    return await create_post(
        db=db,
        author_id=current_user.id,
        post_in=post_in,
    )


@router.post(
    "/compose",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            user_rate_limit(
                scope="posts:create",
                limit=settings.RATE_LIMIT_POST_WRITE_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_POST_WRITE_WINDOW_SECONDS,
            )
        )
    ],
)
async def compose_post_endpoint(
        db: DBSession,
        current_user: CurrentUser,
        content: Annotated[str | None, Form()] = None,
        visibility: Annotated[PostVisibility, Form()] = PostVisibility.PUBLIC,
        image: Annotated[UploadFile | None, File(description="Optional image file for the post")] = None,
) -> PostResponse:
    if image is not None and not image.filename:
        image = None

    image_url = None
    if image is not None:
        uploaded = await upload_post_image(
            user_id=current_user.id,
            file=image,
        )
        image_url = uploaded.url

    try:
        return await create_post_with_optional_content(
            db=db,
            author_id=current_user.id,
            content=content,
            image_url=image_url,
            visibility=visibility,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=PostFeedPage,
    status_code=status.HTTP_200_OK,
)
async def list_posts_endpoint(
        db: DBSession,
        current_user: CurrentUser,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None),
) -> PostFeedPage:
    try:
        return await list_feed_posts(
            db=db,
            viewer_id=current_user.id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
