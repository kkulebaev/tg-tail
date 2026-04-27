"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("channels.id"),
            nullable=False,
        ),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edit_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("entities", postgresql.JSONB(), nullable=True),
        sa.Column("media_type", sa.String(length=32), nullable=True),
        sa.Column(
            "media_status",
            sa.String(length=32),
            nullable=False,
            server_default="none",
        ),
        sa.Column("media_meta", postgresql.JSONB(), nullable=True),
        sa.Column("media_storage_url", sa.Text(), nullable=True),
        sa.Column(
            "media_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("media_last_error", sa.Text(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("forwards", sa.Integer(), nullable=True),
        sa.Column("reply_to_msg_id", sa.BigInteger(), nullable=True),
        sa.Column("grouped_id", sa.BigInteger(), nullable=True),
        sa.Column("post_author", sa.String(length=255), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("channel_id", "message_id", name="uq_messages_channel_message"),
    )

    op.create_index(
        "ix_messages_channel_date",
        "messages",
        ["channel_id", "date"],
    )
    op.create_index(
        "ix_messages_media_pending",
        "messages",
        ["media_status"],
        postgresql_where=sa.text("media_status IN ('pending', 'failed')"),
    )


def downgrade() -> None:
    op.drop_index("ix_messages_media_pending", table_name="messages")
    op.drop_index("ix_messages_channel_date", table_name="messages")
    op.drop_table("messages")
    op.drop_table("channels")
