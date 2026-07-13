import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.post import PostVisibility


class PostAuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str


class PostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    image_url: str | None = Field(default=None, max_length=2048)
    visibility: PostVisibility = PostVisibility.PUBLIC


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    content: str
    image_url: str | None
    visibility: PostVisibility
    author: PostAuthorResponse
    like_count: int
    comment_count: int
    liked_by_me: bool
    created_at: datetime
    updated_at: datetime


class PostFeedPage(BaseModel):
    items: list[PostResponse]
    next_cursor: str | None
    has_more: bool
