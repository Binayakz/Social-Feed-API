from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.post import PostCreate, PostResponse
from app.services.post_service import create_post, list_feed_posts

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
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


@router.get(
    "",
    response_model=list[PostResponse],
    status_code=status.HTTP_200_OK,
)
async def list_posts_endpoint(
        db: DBSession,
        current_user: CurrentUser,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
) -> list[PostResponse]:
    return await list_feed_posts(
        db=db,
        viewer_id=current_user.id,
        limit=limit,
        offset=offset,
    )
