from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    MEDIA_STATUS_DONE,
    MEDIA_STATUS_DOWNLOADING,
    MEDIA_STATUS_FAILED,
    MEDIA_STATUS_NONE,
    MEDIA_STATUS_PENDING,
    MEDIA_STATUS_SKIPPED_TOO_LARGE,
    Channel,
    Message,
)


async def upsert_channel(
    session: AsyncSession,
    *,
    channel_id: int,
    username: str | None,
    title: str | None,
) -> None:
    stmt = (
        pg_insert(Channel)
        .values(id=channel_id, username=username, title=title)
        .on_conflict_do_update(
            index_elements=[Channel.id],
            set_={"username": username, "title": title},
        )
    )
    await session.execute(stmt)


def _resolve_initial_media_status(
    *, has_media: bool, size_bytes: int | None, max_bytes: int
) -> str:
    if not has_media:
        return MEDIA_STATUS_NONE
    if max_bytes > 0 and size_bytes is not None and size_bytes > max_bytes:
        return MEDIA_STATUS_SKIPPED_TOO_LARGE
    return MEDIA_STATUS_PENDING


async def upsert_message(
    session: AsyncSession,
    *,
    parsed: dict[str, Any],
    media_max_bytes: int,
) -> None:
    """Insert a message; on conflict, update only edit-affected fields.

    Media-related columns are set once on insert and never touched by edits.
    """
    has_media = bool(parsed.get("_has_media"))
    size_bytes = parsed.get("_media_size_bytes")
    initial_status = _resolve_initial_media_status(
        has_media=has_media, size_bytes=size_bytes, max_bytes=media_max_bytes
    )

    values = {k: v for k, v in parsed.items() if not k.startswith("_")}
    values["media_status"] = initial_status

    update_set = {
        "edit_date": values["edit_date"],
        "text": values["text"],
        "entities": values["entities"],
        "views": values["views"],
        "forwards": values["forwards"],
        "raw": values["raw"],
        "updated_at": func.now(),
    }

    stmt = (
        pg_insert(Message)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_messages_channel_message",
            set_=update_set,
        )
    )
    await session.execute(stmt)


async def fetch_pending_media(session: AsyncSession, limit: int) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.media_status == MEDIA_STATUS_PENDING)
        .order_by(Message.date)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_media_downloading(session: AsyncSession, message_pk: int) -> None:
    await session.execute(
        update(Message)
        .where(Message.id == message_pk)
        .values(media_status=MEDIA_STATUS_DOWNLOADING)
    )


async def mark_media_done(session: AsyncSession, message_pk: int, *, storage_url: str) -> None:
    await session.execute(
        update(Message)
        .where(Message.id == message_pk)
        .values(
            media_status=MEDIA_STATUS_DONE,
            media_storage_url=storage_url,
            media_last_error=None,
        )
    )


async def mark_media_failed_or_retry(
    session: AsyncSession,
    message_pk: int,
    *,
    error: str,
    max_attempts: int,
) -> str:
    msg = (await session.execute(select(Message).where(Message.id == message_pk))).scalar_one()
    attempts = msg.media_attempts + 1
    new_status = MEDIA_STATUS_FAILED if attempts >= max_attempts else MEDIA_STATUS_PENDING
    await session.execute(
        update(Message)
        .where(Message.id == message_pk)
        .values(
            media_status=new_status,
            media_attempts=attempts,
            media_last_error=error,
        )
    )
    return new_status
