import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class PostVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class Post(TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_author_created_at", "author_id", "created_at"),
        Index("ix_posts_visibility_created_at", "visibility", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    visibility: Mapped[PostVisibility] = mapped_column(
        SQLEnum(PostVisibility, name="post_visibility"),
        nullable=False,
        default=PostVisibility.PUBLIC,
    )

    author: Mapped["User"] = relationship(back_populates="posts")
