import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Post, PostVisibility
from app.schemas.post import PostAuthorResponse, PostCreate, PostResponse


def build_post_response(post: Post, viewer_id: uuid.UUID) -> PostResponse:
    return PostResponse(
        id=post.id,
        author_id=post.author_id,
        content=post.content,
        image_url=post.image_url,
        visibility=post.visibility,
        author=PostAuthorResponse.model_validate(post.author),
        like_count=len(post.likes),
        comment_count=len(post.comments),
        liked_by_me=any(like.user_id == viewer_id for like in post.likes),
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


async def create_post(
        db: AsyncSession,
        author_id: uuid.UUID,
        post_in: PostCreate,
) -> Post:
    post = Post(
        author_id=author_id,
        content=post_in.content,
        image_url=post_in.image_url,
        visibility=post_in.visibility,
    )

    db.add(post)
    await db.commit()

    result = await db.execute(
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.likes),
            selectinload(Post.comments),
        )
        .where(Post.id == post.id)
    )
    return result.scalar_one()


async def get_post_by_id_for_viewer(
        db: AsyncSession,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> Post | None:
    result = await db.execute(
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.likes),
            selectinload(Post.comments),
        )
        .where(Post.id == post_id)
        .where(
            or_(
                Post.visibility == PostVisibility.PUBLIC,
                Post.author_id == viewer_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def list_feed_posts(
        db: AsyncSession,
        viewer_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
) -> list[Post]:
    result = await db.execute(
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.likes),
            selectinload(Post.comments),
        )
        .where(
            or_(
                Post.visibility == PostVisibility.PUBLIC,
                Post.author_id == viewer_id,
            )
        )
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all())
