import base64
import binascii
import json
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, func, or_, select
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


def _serialize_reply_row(
        row,
        likers_preview: list[CommentLikerPreview] | None = None,
) -> ReplyResponse:
    reply: Comment = row[0]

    return ReplyResponse(
        id=reply.id,
        post_id=reply.post_id,
        author_id=reply.author_id,
        parent_id=reply.parent_id,
        content=reply.content,
        author=CommentAuthorResponse.model_validate(reply.author),
        like_count=int(row.like_count or 0),
        liked_by_me=bool(row.liked_by_me),
        likers_preview=likers_preview or [],
        created_at=reply.created_at,
        updated_at=reply.updated_at,
    )


def _serialize_comment_row(
        row,
        replies: list[ReplyResponse] | None = None,
        likers_preview: list[CommentLikerPreview] | None = None,
) -> CommentResponse:
    comment: Comment = row[0]

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        parent_id=comment.parent_id,
        content=comment.content,
        author=CommentAuthorResponse.model_validate(comment.author),
        like_count=int(row.like_count or 0),
        liked_by_me=bool(row.liked_by_me),
        likers_preview=likers_preview or [],
        replies=replies or [],
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


def _build_comment_stmt(viewer_id: uuid.UUID):
    like_count_subquery = (
        select(
            CommentLike.comment_id.label("comment_id"),
            func.count(CommentLike.id).label("like_count"),
        )
        .group_by(CommentLike.comment_id)
        .subquery()
    )

    liked_by_me_expr = (
        select(CommentLike.id)
        .where(
            CommentLike.comment_id == Comment.id,
            CommentLike.user_id == viewer_id,
        )
        .exists()
    )

    return (
        select(
            Comment,
            func.coalesce(like_count_subquery.c.like_count, 0).label("like_count"),
            liked_by_me_expr.label("liked_by_me"),
        )
        .options(selectinload(Comment.author))
        .outerjoin(
            like_count_subquery,
            like_count_subquery.c.comment_id == Comment.id,
        )
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


async def _get_reply_rows_for_parents(
        db: AsyncSession,
        parent_ids: list[uuid.UUID],
        viewer_id: uuid.UUID,
):
    if not parent_ids:
        return []

    stmt = (
        _build_comment_stmt(viewer_id)
        .where(Comment.parent_id.in_(parent_ids))
        .order_by(Comment.parent_id.asc(), Comment.created_at.asc(), Comment.id.asc())
    )

    result = await db.execute(stmt)
    return result.all()


async def _build_comment_response_by_id(
        db: AsyncSession,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID,
) -> CommentResponse | None:
    stmt = _build_comment_stmt(viewer_id).where(Comment.id == comment_id)

    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is None:
        return None

    comment: Comment = row[0]
    reply_rows = []

    if comment.parent_id is None:
        reply_rows = await _get_reply_rows_for_parents(
            db=db,
            parent_ids=[comment.id],
            viewer_id=viewer_id,
        )

    comment_ids = [comment.id] + [reply_row[0].id for reply_row in reply_rows]
    preview_map = await _get_comment_likers_preview_map(db, comment_ids)

    replies = [
        _serialize_reply_row(
            reply_row,
            likers_preview=preview_map.get(reply_row[0].id, []),
        )
        for reply_row in reply_rows
    ]

    return _serialize_comment_row(
        row,
        replies=replies,
        likers_preview=preview_map.get(comment.id, []),
    )


async def create_comment(
        db: AsyncSession,
        post_id: uuid.UUID,
        author_id: uuid.UUID,
        comment_in: CommentCreate,
) -> CommentResponse:
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

    created_comment = await _build_comment_response_by_id(
        db=db,
        comment_id=comment.id,
        viewer_id=author_id,
    )
    if created_comment is None:
        raise LookupError("Created comment could not be loaded")

    return created_comment


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
        _build_comment_stmt(viewer_id)
        .where(Comment.post_id == post_id)
        .where(Comment.parent_id.is_(None))
        .order_by(Comment.created_at.desc(), Comment.id.desc())
    )

    if cursor:
        stmt = stmt.where(_comment_cursor_clause(cursor))

    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    visible_rows = rows[:limit]

    parent_ids = [row[0].id for row in visible_rows]
    reply_rows = await _get_reply_rows_for_parents(
        db=db,
        parent_ids=parent_ids,
        viewer_id=viewer_id,
    )

    comment_ids = parent_ids + [reply_row[0].id for reply_row in reply_rows]
    preview_map = await _get_comment_likers_preview_map(db, comment_ids)

    replies_by_parent: dict[uuid.UUID, list[ReplyResponse]] = defaultdict(list)
    for reply_row in reply_rows:
        reply: Comment = reply_row[0]
        if reply.parent_id is None:
            continue

        replies_by_parent[reply.parent_id].append(
            _serialize_reply_row(
                reply_row,
                likers_preview=preview_map.get(reply.id, []),
            )
        )

    next_cursor = None
    if has_more and visible_rows:
        last_comment = visible_rows[-1][0]
        next_cursor = _encode_cursor(last_comment.created_at, last_comment.id)

    return CommentPage(
        items=[
            _serialize_comment_row(
                row,
                replies=replies_by_parent.get(row[0].id, []),
                likers_preview=preview_map.get(row[0].id, []),
            )
            for row in visible_rows
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )
