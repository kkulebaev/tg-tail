from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


MEDIA_STATUS_NONE = "none"
MEDIA_STATUS_PENDING = "pending"
MEDIA_STATUS_DOWNLOADING = "downloading"
MEDIA_STATUS_DONE = "done"
MEDIA_STATUS_FAILED = "failed"
MEDIA_STATUS_SKIPPED_TOO_LARGE = "skipped_too_large"


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id"), nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text: Mapped[str | None] = mapped_column(Text)
    entities: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    media_type: Mapped[str | None] = mapped_column(String(32))
    media_status: Mapped[str] = mapped_column(String(32), nullable=False, default=MEDIA_STATUS_NONE)
    media_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    media_storage_url: Mapped[str | None] = mapped_column(Text)
    media_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_last_error: Mapped[str | None] = mapped_column(Text)
    views: Mapped[int | None] = mapped_column(Integer)
    forwards: Mapped[int | None] = mapped_column(Integer)
    reply_to_msg_id: Mapped[int | None] = mapped_column(BigInteger)
    grouped_id: Mapped[int | None] = mapped_column(BigInteger)
    post_author: Mapped[str | None] = mapped_column(String(255))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_messages_channel_message"),
        Index("ix_messages_channel_date", "channel_id", "date"),
        Index(
            "ix_messages_media_pending",
            "media_status",
            postgresql_where=sa_text("media_status IN ('pending', 'failed')"),
        ),
    )
