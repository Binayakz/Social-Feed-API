import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.comment import CommentCreate, CommentPage, CommentResponse
from app.services.comment_service import create_comment, list_post_comments

router = APIRouter(prefix="/posts", tags=["comments"])


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment_endpoint(
        post_id: uuid.UUID,
        comment_in: CommentCreate,
        db: DBSession,
        current_user: CurrentUser,
) -> CommentResponse:
    try:
        comment = await create_comment(
            db=db,
            post_id=post_id,
            author_id=current_user.id,
            comment_in=comment_in,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    from app.services.comment_service import build_comment_response

    return build_comment_response(comment, current_user.id)


@router.get(
    "/{post_id}/comments",
    response_model=CommentPage,
    status_code=status.HTTP_200_OK,
)
async def list_post_comments_endpoint(
        post_id: uuid.UUID,
        db: DBSession,
        current_user: CurrentUser,
        limit: int = Query(default=20, ge=1, le=100),
        cursor: str | None = Query(default=None),
) -> CommentPage:
    try:
        return await list_post_comments(
            db=db,
            post_id=post_id,
            viewer_id=current_user.id,
            limit=limit,
            cursor=cursor,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
