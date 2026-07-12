import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, Post, PostVisibility
from app.schemas.comment import (
    CommentAuthorResponse,
    CommentCreate,
    CommentResponse,
    ReplyResponse,
)


def build_reply_response(reply: Comment, viewer_id: uuid.UUID) -> ReplyResponse:
    return ReplyResponse(
        id=reply.id,
        post_id=reply.post_id,
        author_id=reply.author_id,
        parent_id=reply.parent_id,
        content=reply.content,
        author=CommentAuthorResponse.model_validate(reply.author),
        like_count=len(reply.likes),
        liked_by_me=any(like.user_id == viewer_id for like in reply.likes),
        created_at=reply.created_at,
        updated_at=reply.updated_at,
    )


def build_comment_response(comment: Comment, viewer_id: uuid.UUID) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        parent_id=comment.parent_id,
        content=comment.content,
        author=CommentAuthorResponse.model_validate(comment.author),
        like_count=len(comment.likes),
        liked_by_me=any(like.user_id == viewer_id for like in comment.likes),
        replies=[build_reply_response(reply, viewer_id) for reply in comment.replies],
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


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
            select(Comment)
            .where(Comment.id == comment_in.parent_id)
            .where(Comment.post_id == post_id)
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
        .options(
            selectinload(Comment.author),
            selectinload(Comment.likes),
            selectinload(Comment.replies).selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.likes),
        )
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
            selectinload(Comment.likes),
            selectinload(Comment.replies).selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.likes),
        )
        .where(Comment.post_id == post_id)
        .where(Comment.parent_id.is_(None))
        .order_by(Comment.created_at.asc())
    )
    return list(result.scalars().unique().all())
