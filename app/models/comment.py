import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User
    from app.models.comment_like import CommentLike


class Comment(TimestampMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index(
            "ix_comments_post_parent_created_at_id_desc",
            "post_id",
            "parent_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_comments_post_created_at_id_desc",
            "post_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_comments_author_created_at",
            "author_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    post: Mapped["Post"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")
    parent: Mapped["Comment | None"] = relationship(
        back_populates="replies",
        remote_side="Comment.id",
    )
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent",
        passive_deletes=True,
        order_by="Comment.created_at",
    )
    likes: Mapped[list["CommentLike"]] = relationship(
        back_populates="comment",
        passive_deletes=True,
    )
