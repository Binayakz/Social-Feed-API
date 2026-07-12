import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, CommentLike, Post, PostLike, PostVisibility, User


async def _get_visible_post(
        db: AsyncSession,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> Post | None:
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
        .where(
            or_(
                Post.visibility == PostVisibility.PUBLIC,
                Post.author_id == viewer_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def _get_visible_comment(
        db: AsyncSession,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> Comment | None:
    result = await db.execute(
        select(Comment)
        .join(Post, Comment.post_id == Post.id)
        .where(Comment.id == comment_id)
        .where(
            or_(
                Post.visibility == PostVisibility.PUBLIC,
                Post.author_id == viewer_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def _count_post_likes(db: AsyncSession, post_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(PostLike.id)).where(PostLike.post_id == post_id)
    )
    return int(result.scalar_one())


async def _count_comment_likes(db: AsyncSession, comment_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(CommentLike.id)).where(CommentLike.comment_id == comment_id)
    )
    return int(result.scalar_one())


async def like_post(
        db: AsyncSession,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
) -> int:
    post = await _get_visible_post(db, post_id=post_id, viewer_id=user_id)
    if post is None:
        raise LookupError("Post not found")

    existing = await db.execute(
        select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
    )
    like = existing.scalar_one_or_none()

    if like is None:
        db.add(PostLike(post_id=post_id, user_id=user_id))
        await db.commit()

    return await _count_post_likes(db, post_id)


async def unlike_post(
        db: AsyncSession,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
) -> int:
    post = await _get_visible_post(db, post_id=post_id, viewer_id=user_id)
    if post is None:
        raise LookupError("Post not found")

    existing = await db.execute(
        select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        )
    )
    like = existing.scalar_one_or_none()

    if like is not None:
        await db.delete(like)
        await db.commit()

    return await _count_post_likes(db, post_id)


async def list_post_likers(
        db: AsyncSession,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> list[User]:
    post = await _get_visible_post(db, post_id=post_id, viewer_id=viewer_id)
    if post is None:
        raise LookupError("Post not found")

    result = await db.execute(
        select(User)
        .join(PostLike, PostLike.user_id == User.id)
        .where(PostLike.post_id == post_id)
        .order_by(PostLike.created_at.asc())
    )
    return list(result.scalars().all())


async def like_comment(
        db: AsyncSession,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
) -> int:
    comment = await _get_visible_comment(db, comment_id=comment_id, viewer_id=user_id)
    if comment is None:
        raise LookupError("Comment not found")

    existing = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == user_id,
        )
    )
    like = existing.scalar_one_or_none()

    if like is None:
        db.add(CommentLike(comment_id=comment_id, user_id=user_id))
        await db.commit()

    return await _count_comment_likes(db, comment_id)


async def unlike_comment(
        db: AsyncSession,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
) -> int:
    comment = await _get_visible_comment(db, comment_id=comment_id, viewer_id=user_id)
    if comment is None:
        raise LookupError("Comment not found")

    existing = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == user_id,
        )
    )
    like = existing.scalar_one_or_none()

    if like is not None:
        await db.delete(like)
        await db.commit()

    return await _count_comment_likes(db, comment_id)


async def list_comment_likers(
        db: AsyncSession,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> list[User]:
    comment = await _get_visible_comment(db, comment_id=comment_id, viewer_id=viewer_id)
    if comment is None:
        raise LookupError("Comment not found")

    result = await db.execute(
        select(User)
        .join(CommentLike, CommentLike.user_id == User.id)
        .where(CommentLike.comment_id == comment_id)
        .order_by(CommentLike.created_at.asc())
    )
    return list(result.scalars().all())
