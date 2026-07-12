import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentAuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    parent_id: uuid.UUID | None = None


class ReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID
    parent_id: uuid.UUID | None
    content: str
    author: CommentAuthorResponse
    created_at: datetime
    updated_at: datetime


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID
    parent_id: uuid.UUID | None
    content: str
    author: CommentAuthorResponse
    replies: list[ReplyResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime