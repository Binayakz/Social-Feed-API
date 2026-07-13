import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, Post, PostLike, PostVisibility
from app.schemas.post import PostAuthorResponse, PostCreate, PostResponse


def _visibility_clause(viewer_id: uuid.UUID):
    return or_(
        Post.visibility == PostVisibility.PUBLIC,
        Post.author_id == viewer_id,
    )


def _serialize_post_row(row) -> PostResponse:
    post: Post = row[0]

    return PostResponse(
        id=post.id,
        author_id=post.author_id,
        content=post.content,
        image_url=post.image_url,
        visibility=post.visibility,
        author=PostAuthorResponse.model_validate(post.author),
        like_count=int(row.like_count or 0),
        comment_count=int(row.comment_count or 0),
        liked_by_me=bool(row.liked_by_me),
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _build_feed_stmt(viewer_id: uuid.UUID):
    like_count_subquery = (
        select(
            PostLike.post_id.label("post_id"),
            func.count(PostLike.id).label("like_count"),
        )
        .group_by(PostLike.post_id)
        .subquery()
    )

    comment_count_subquery = (
        select(
            Comment.post_id.label("post_id"),
            func.count(Comment.id).label("comment_count"),
        )
        .group_by(Comment.post_id)
        .subquery()
    )

    liked_by_me_expr = (
        select(PostLike.id)
        .where(
            PostLike.post_id == Post.id,
            PostLike.user_id == viewer_id,
        )
        .exists()
    )

    return (
        select(
            Post,
            func.coalesce(like_count_subquery.c.like_count, 0).label("like_count"),
            func.coalesce(comment_count_subquery.c.comment_count, 0).label("comment_count"),
            liked_by_me_expr.label("liked_by_me"),
        )
        .options(selectinload(Post.author))
        .outerjoin(
            like_count_subquery,
            like_count_subquery.c.post_id == Post.id,
        )
        .outerjoin(
            comment_count_subquery,
            comment_count_subquery.c.post_id == Post.id,
        )
    )


async def create_post(
        db: AsyncSession,
        author_id: uuid.UUID,
        post_in: PostCreate,
) -> PostResponse:
    post = Post(
        author_id=author_id,
        content=post_in.content,
        image_url=post_in.image_url,
        visibility=post_in.visibility,
    )

    db.add(post)
    await db.commit()

    created_post = await get_post_by_id_for_viewer(
        db=db,
        post_id=post.id,
        viewer_id=author_id,
    )
    if created_post is None:
        raise LookupError("Created post could not be loaded")

    return created_post


async def get_post_by_id_for_viewer(
        db: AsyncSession,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> PostResponse | None:
    stmt = (
        _build_feed_stmt(viewer_id)
        .where(Post.id == post_id)
        .where(_visibility_clause(viewer_id))
    )

    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is None:
        return None

    return _serialize_post_row(row)


async def list_feed_posts(
        db: AsyncSession,
        viewer_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
) -> list[PostResponse]:
    stmt = (
        _build_feed_stmt(viewer_id)
        .where(_visibility_clause(viewer_id))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [_serialize_post_row(row) for row in rows]
