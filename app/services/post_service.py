import base64
import json
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, Post, PostLike, PostVisibility, User
from app.schemas.post import (
    PostAuthorResponse,
    PostCreate,
    PostFeedPage,
    PostLikerPreview,
    PostResponse,
)

POST_LIKERS_PREVIEW_LIMIT = 3


def _visibility_clause(viewer_id: uuid.UUID):
    return or_(
        Post.visibility == PostVisibility.PUBLIC,
        Post.author_id == viewer_id,
    )


def _build_initials(first_name: str, last_name: str) -> str:
    first = first_name[:1].upper() if first_name else ""
    last = last_name[:1].upper() if last_name else ""
    return f"{first}{last}" or "?"


def _serialize_post_row(
        row,
        likers_preview: list[PostLikerPreview] | None = None,
) -> PostResponse:
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
        likers_preview=likers_preview or [],
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


def _encode_cursor(created_at: datetime, post_id: uuid.UUID) -> str:
    payload = {
        "created_at": created_at.isoformat(),
        "id": str(post_id),
    }
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw)
        created_at = datetime.fromisoformat(payload["created_at"])
        post_id = uuid.UUID(payload["id"])
        return created_at, post_id
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc


def _cursor_clause(cursor: str):
    cursor_created_at, cursor_post_id = _decode_cursor(cursor)

    return or_(
        Post.created_at < cursor_created_at,
        and_(
            Post.created_at == cursor_created_at,
            Post.id < cursor_post_id,
        ),
    )


async def _get_post_likers_preview_map(
        db: AsyncSession,
        post_ids: list[uuid.UUID],
        preview_limit: int = POST_LIKERS_PREVIEW_LIMIT,
) -> dict[uuid.UUID, list[PostLikerPreview]]:
    if not post_ids:
        return {}

    result = await db.execute(
        select(PostLike.post_id, User)
        .join(User, User.id == PostLike.user_id)
        .where(PostLike.post_id.in_(post_ids))
        .order_by(PostLike.post_id, PostLike.created_at.desc(), PostLike.id.desc())
    )

    preview_map: dict[uuid.UUID, list[PostLikerPreview]] = defaultdict(list)

    for post_id, user in result.all():
        if len(preview_map[post_id]) >= preview_limit:
            continue

        preview_map[post_id].append(
            PostLikerPreview(
                id=user.id,
                full_name=user.full_name,
                initials=_build_initials(user.first_name, user.last_name),
                profile_image_url=user.profile_image_url,
            )
        )

    return dict(preview_map)


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

    preview_map = await _get_post_likers_preview_map(db, [post_id])

    return _serialize_post_row(
        row,
        likers_preview=preview_map.get(post_id, []),
    )


async def list_feed_posts(
        db: AsyncSession,
        viewer_id: uuid.UUID,
        limit: int = 20,
        cursor: str | None = None,
) -> PostFeedPage:
    stmt = (
        _build_feed_stmt(viewer_id)
        .where(_visibility_clause(viewer_id))
        .order_by(Post.created_at.desc(), Post.id.desc())
    )

    if cursor:
        stmt = stmt.where(_cursor_clause(cursor))

    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    visible_rows = rows[:limit]

    post_ids = [row[0].id for row in visible_rows]
    preview_map = await _get_post_likers_preview_map(db, post_ids)

    items = [
        _serialize_post_row(
            row,
            likers_preview=preview_map.get(row[0].id, []),
        )
        for row in visible_rows
    ]

    next_cursor = None
    if has_more and visible_rows:
        last_post = visible_rows[-1][0]
        next_cursor = _encode_cursor(last_post.created_at, last_post.id)

    return PostFeedPage(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )
