import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, Post, PostVisibility
from app.schemas.comment import CommentCreate


async def _get_visible_post(
        db: AsyncSession,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> Post | None:
    result = await db.execute(
        select(Post).where(Post.id == post_id).where(
            or_(
                Post.visibility == PostVisibility.PUBLIC,
                Post.author_id == viewer_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def create_comment(
        db: AsyncSession,
        post_id: uuid.UUID,
        author_id: uuid.UUID,
        comment_in: CommentCreate,
) -> Comment:
    post = await _get_visible_post(db, post_id=post_id, viewer_id=author_id)
    if post is None:
        raise LookupError("Post not found")

    if comment_in.parent_id is not None:
        parent_result = await db.execute(
            select(Comment).where(Comment.id == comment_in.parent_id).where(Comment.post_id == post_id)
        )
        parent_comment = parent_result.scalar_one_or_none()

        if parent_comment is None:
            raise LookupError("Parent comment not found")

        if parent_comment.parent_id is not None:
            raise ValueError("Only one level of replies is supported")

    comment = Comment(
        post_id=post_id,
        author_id=author_id,
        parent_id=comment_in.parent_id,
        content=comment_in.content,
    )

    db.add(comment)
    await db.commit()

    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.author), selectinload(Comment.replies).selectinload(Comment.author))
        .where(Comment.id == comment.id)
    )
    return result.scalar_one()


async def list_post_comments(
        db: AsyncSession,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> list[Comment]:
    post = await _get_visible_post(db, post_id=post_id, viewer_id=viewer_id)
    if post is None:
        raise LookupError("Post not found")

    result = await db.execute(
        select(Comment)
        .options(
            selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.author),
        )
        .where(Comment.post_id == post_id)
        .where(Comment.parent_id.is_(None))
        .order_by(Comment.created_at.asc())
    )
    return list(result.scalars().unique().all())
