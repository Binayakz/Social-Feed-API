import base64
import binascii
import json
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, CommentLike, Post, PostVisibility, User
from app.schemas.comment import (
    CommentAuthorResponse,
    CommentCreate,
    CommentLikerPreview,
    CommentPage,
    CommentResponse,
    ReplyResponse,
)

COMMENT_LIKERS_PREVIEW_LIMIT = 3


def _build_initials(first_name: str, last_name: str) -> str:
    first = first_name[:1].upper() if first_name else ""
    last = last_name[:1].upper() if last_name else ""
    return f"{first}{last}" or "?"


def build_reply_response(
        reply: Comment,
        viewer_id: uuid.UUID,
        likers_preview: list[CommentLikerPreview] | None = None,
) -> ReplyResponse:
    return ReplyResponse(
        id=reply.id,
        post_id=reply.post_id,
        author_id=reply.author_id,
        parent_id=reply.parent_id,
        content=reply.content,
        author=CommentAuthorResponse.model_validate(reply.author),
        like_count=len(reply.likes),
        liked_by_me=any(like.user_id == viewer_id for like in reply.likes),
        likers_preview=likers_preview or [],
        created_at=reply.created_at,
        updated_at=reply.updated_at,
    )


def build_comment_response(
        comment: Comment,
        viewer_id: uuid.UUID,
        preview_map: dict[uuid.UUID, list[CommentLikerPreview]] | None = None,
) -> CommentResponse:
    preview_map = preview_map or {}

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        parent_id=comment.parent_id,
        content=comment.content,
        author=CommentAuthorResponse.model_validate(comment.author),
        like_count=len(comment.likes),
        liked_by_me=any(like.user_id == viewer_id for like in comment.likes),
        likers_preview=preview_map.get(comment.id, []),
        replies=[
            build_reply_response(
                reply,
                viewer_id,
                likers_preview=preview_map.get(reply.id, []),
            )
            for reply in comment.replies
        ],
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def _encode_cursor(created_at: datetime, comment_id: uuid.UUID) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(comment_id),
    }
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw)
        created_at = datetime.fromisoformat(payload["created_at"])
        comment_id = uuid.UUID(payload["id"])
        return created_at, comment_id
    except (ValueError, KeyError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("Invalid cursor") from exc


def _comment_cursor_clause(cursor: str):
    cursor_created_at, cursor_comment_id = _decode_cursor(cursor)

    return or_(
        Comment.created_at < cursor_created_at,
        and_(
            Comment.created_at == cursor_created_at,
            Comment.id < cursor_comment_id,
        ),
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


async def _get_comment_likers_preview_map(
        db: AsyncSession,
        comment_ids: list[uuid.UUID],
        preview_limit: int = COMMENT_LIKERS_PREVIEW_LIMIT,
) -> dict[uuid.UUID, list[CommentLikerPreview]]:
    if not comment_ids:
        return {}

    result = await db.execute(
        select(CommentLike.comment_id, User)
        .join(User, User.id == CommentLike.user_id)
        .where(CommentLike.comment_id.in_(comment_ids))
        .order_by(CommentLike.comment_id, CommentLike.created_at.desc(), CommentLike.id.desc())
    )

    preview_map: dict[uuid.UUID, list[CommentLikerPreview]] = defaultdict(list)

    for comment_id, user in result.all():
        if len(preview_map[comment_id]) >= preview_limit:
            continue

        preview_map[comment_id].append(
            CommentLikerPreview(
                id=user.id,
                full_name=user.full_name,
                initials=_build_initials(user.first_name, user.last_name),
            )
        )

    return dict(preview_map)


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
        limit: int = 20,
        cursor: str | None = None,
) -> CommentPage:
    post = await _get_visible_post(db, post_id=post_id, viewer_id=viewer_id)
    if post is None:
        raise LookupError("Post not found")

    stmt = (
        select(Comment)
        .options(
            selectinload(Comment.author),
            selectinload(Comment.likes),
            selectinload(Comment.replies).selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.likes),
        )
        .where(Comment.post_id == post_id)
        .where(Comment.parent_id.is_(None))
        .order_by(Comment.created_at.desc(), Comment.id.desc())
    )

    if cursor:
        stmt = stmt.where(_comment_cursor_clause(cursor))

    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    comments = list(result.scalars().unique().all())

    has_more = len(comments) > limit
    visible_comments = comments[:limit]

    comment_ids: list[uuid.UUID] = []
    for comment in visible_comments:
        comment_ids.append(comment.id)
        comment_ids.extend(reply.id for reply in comment.replies)

    preview_map = await _get_comment_likers_preview_map(db, comment_ids)

    next_cursor = None
    if has_more and visible_comments:
        last_comment = visible_comments[-1]
        next_cursor = _encode_cursor(last_comment.created_at, last_comment.id)

    return CommentPage(
        items=[
            build_comment_response(
                comment,
                viewer_id,
                preview_map=preview_map,
            )
            for comment in visible_comments
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )
