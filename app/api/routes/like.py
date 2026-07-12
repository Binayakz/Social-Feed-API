import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.like import LikeActionResponse, LikeListResponse
from app.services.like_service import (
    like_comment,
    like_post,
    list_comment_likers,
    list_post_likers,
    unlike_comment,
    unlike_post,
)

router = APIRouter(tags=["likes"])


@router.post(
    "/posts/{post_id}/like",
    response_model=LikeActionResponse,
    status_code=status.HTTP_200_OK,
)
async def like_post_endpoint(
        post_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
) -> LikeActionResponse:
    try:
        count = await like_post(db=db, post_id=post_id, user_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LikeActionResponse(liked=True, count=count)


@router.delete(
    "/posts/{post_id}/like",
    response_model=LikeActionResponse,
    status_code=status.HTTP_200_OK,
)
async def unlike_post_endpoint(
        post_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
) -> LikeActionResponse:
    try:
        count = await unlike_post(db=db, post_id=post_id, user_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LikeActionResponse(liked=False, count=count)


@router.get(
    "/posts/{post_id}/likes",
    response_model=LikeListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_post_likers_endpoint(
        post_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
) -> LikeListResponse:
    try:
        users = await list_post_likers(db=db, post_id=post_id, viewer_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LikeListResponse(count=len(users), users=users)


@router.post(
    "/comments/{comment_id}/like",
    response_model=LikeActionResponse,
    status_code=status.HTTP_200_OK,
)
async def like_comment_endpoint(
        comment_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
) -> LikeActionResponse:
    try:
        count = await like_comment(db=db, comment_id=comment_id, user_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LikeActionResponse(liked=True, count=count)


@router.delete(
    "/comments/{comment_id}/like",
    response_model=LikeActionResponse,
    status_code=status.HTTP_200_OK,
)
async def unlike_comment_endpoint(
        comment_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
) -> LikeActionResponse:
    try:
        count = await unlike_comment(db=db, comment_id=comment_id, user_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LikeActionResponse(liked=False, count=count)


@router.get(
    "/comments/{comment_id}/likes",
    response_model=LikeListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_comment_likers_endpoint(
        comment_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
) -> LikeListResponse:
    try:
        users = await list_comment_likers(
            db=db,
            comment_id=comment_id,
            viewer_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LikeListResponse(count=len(users), users=users)
