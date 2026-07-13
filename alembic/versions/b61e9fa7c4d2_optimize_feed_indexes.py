"""optimize feed indexes

Revision ID: b61e9fa7c4d2
Revises: a30e07558e24
Create Date: 2026-07-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b61e9fa7c4d2"
down_revision: Union[str, Sequence[str], None] = "a30e07558e24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop older, less specific feed indexes.
    op.drop_index("ix_posts_author_created_at", table_name="posts")
    op.drop_index("ix_posts_visibility_created_at", table_name="posts")
    op.drop_index("ix_comments_post_parent_created_at", table_name="comments")

    # Feed index for "my posts" access pattern.
    op.create_index(
        "ix_posts_author_created_at_id_desc",
        "posts",
        ["author_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )

    # Partial index for public feed reads.
    # Important: the enum values in your current DB migration are PUBLIC/PRIVATE.
    op.create_index(
        "ix_posts_public_created_at_id_desc",
        "posts",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
        postgresql_where=sa.text("visibility = 'PUBLIC'"),
    )

    # Supports top-level comments and replies by post + parent + newest-first order.
    op.create_index(
        "ix_comments_post_parent_created_at_id_desc",
        "comments",
        ["post_id", "parent_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )

    # Supports post-level comment scans/count-oriented access and future comment pagination.
    op.create_index(
        "ix_comments_post_created_at_id_desc",
        "comments",
        ["post_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_comments_post_created_at_id_desc", table_name="comments")
    op.drop_index("ix_comments_post_parent_created_at_id_desc", table_name="comments")
    op.drop_index("ix_posts_public_created_at_id_desc", table_name="posts")
    op.drop_index("ix_posts_author_created_at_id_desc", table_name="posts")

    op.create_index(
        "ix_comments_post_parent_created_at",
        "comments",
        ["post_id", "parent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_posts_visibility_created_at",
        "posts",
        ["visibility", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_posts_author_created_at",
        "posts",
        ["author_id", "created_at"],
        unique=False,
    )