import asyncio
from io import BytesIO
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from ..db.models import Message
from ..db.repository import (
    fetch_pending_media,
    mark_media_done,
    mark_media_downloading,
    mark_media_failed_or_retry,
)
from .s3 import S3Client

log = structlog.get_logger(__name__)


def _object_key(msg: Message) -> str:
    d = msg.date
    return f"{d:%Y/%m/%d}/{msg.channel_id}/{msg.message_id}"


def _content_type_from_meta(meta: dict[str, Any] | None) -> str | None:
    if not meta:
        return None
    tl = meta.get("tl") or {}
    doc = tl.get("document") or {}
    mime = doc.get("mime_type")
    if isinstance(mime, str) and mime:
        return mime
    return None


async def _download_one(
    *,
    client: TelegramClient,
    s3: S3Client,
    session_factory: async_sessionmaker[AsyncSession],
    msg: Message,
    max_attempts: int,
) -> None:
    msg_pk = msg.id
    channel_id = msg.channel_id
    message_id = msg.message_id

    async with session_factory() as session:
        await mark_media_downloading(session, msg_pk)
        await session.commit()

    try:
        tg_msg = await client.get_messages(channel_id, ids=message_id)
        if tg_msg is None:
            raise RuntimeError("message no longer accessible")
        if not getattr(tg_msg, "media", None):
            raise RuntimeError("message has no media")

        buf = BytesIO()
        await client.download_media(tg_msg, file=buf)
        data = buf.getvalue()
        if not data:
            raise RuntimeError("empty download")

        key = _object_key(msg)
        content_type = _content_type_from_meta(msg.media_meta)
        storage_url = await s3.put_object(key, data, content_type=content_type)

        async with session_factory() as session:
            await mark_media_done(session, msg_pk, storage_url=storage_url)
            await session.commit()
        log.info(
            "media_downloaded",
            message_pk=msg_pk,
            channel_id=channel_id,
            message_id=message_id,
            bytes=len(data),
            key=key,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        async with session_factory() as session:
            new_status = await mark_media_failed_or_retry(
                session,
                msg_pk,
                error=str(exc)[:500],
                max_attempts=max_attempts,
            )
            await session.commit()
        log.error(
            "media_download_failed",
            message_pk=msg_pk,
            channel_id=channel_id,
            message_id=message_id,
            error=str(exc),
            new_status=new_status,
        )


async def run_downloader(
    *,
    client: TelegramClient,
    s3: S3Client,
    session_factory: async_sessionmaker[AsyncSession],
    concurrency: int,
    poll_interval_seconds: float,
    max_attempts: int,
) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    log.info(
        "downloader_started",
        concurrency=concurrency,
        poll_interval_seconds=poll_interval_seconds,
        max_attempts=max_attempts,
    )

    async def _process(msg: Message) -> None:
        async with semaphore:
            await _download_one(
                client=client,
                s3=s3,
                session_factory=session_factory,
                msg=msg,
                max_attempts=max_attempts,
            )

    while True:
        try:
            async with session_factory() as session:
                pending = await fetch_pending_media(session, limit=concurrency * 5)

            if not pending:
                await asyncio.sleep(poll_interval_seconds)
                continue

            await asyncio.gather(*(_process(m) for m in pending), return_exceptions=True)
        except asyncio.CancelledError:
            log.info("downloader_cancelled")
            raise
        except Exception:
            log.exception("downloader_loop_error")
            await asyncio.sleep(poll_interval_seconds)
