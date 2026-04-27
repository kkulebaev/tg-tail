from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient, events
from telethon.tl.types import Channel as TgChannel

from ..db.repository import upsert_channel, upsert_message
from .parser import parse_message

log = structlog.get_logger(__name__)


async def resolve_and_upsert_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    channel_refs: list[str],
) -> list[int]:
    """Resolve env-supplied refs (numeric IDs or @usernames) to channel IDs.

    Side effect: upserts each resolved channel into the `channels` table.
    Refs that fail to resolve or aren't channels are logged and skipped.
    """
    resolved_ids: list[int] = []
    async with session_factory() as session:
        for ref in channel_refs:
            try:
                target: int | str = int(ref) if ref.lstrip("-").isdigit() else ref
                entity = await client.get_entity(target)
            except Exception as exc:
                log.error("channel_resolve_failed", ref=ref, error=str(exc))
                continue
            if not isinstance(entity, TgChannel):
                log.error("ref_is_not_channel", ref=ref, type=type(entity).__name__)
                continue
            channel_id = int(entity.id)
            await upsert_channel(
                session,
                channel_id=channel_id,
                username=entity.username,
                title=entity.title,
            )
            resolved_ids.append(channel_id)
            log.info(
                "channel_resolved",
                channel_id=channel_id,
                username=entity.username,
                title=entity.title,
            )
        await session.commit()
    return resolved_ids


def register_handlers(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    channel_ids: list[int],
    media_max_bytes: int,
) -> None:
    async def _save(event: Any) -> None:
        msg = event.message
        try:
            parsed = parse_message(msg)
        except ValueError as exc:
            log.warning("skipping_non_channel_message", error=str(exc))
            return
        async with session_factory() as session:
            await upsert_message(session, parsed=parsed, media_max_bytes=media_max_bytes)
            await session.commit()
        log.info(
            "message_saved",
            channel_id=parsed["channel_id"],
            message_id=parsed["message_id"],
            edited=msg.edit_date is not None,
            media_type=parsed["media_type"],
        )

    client.add_event_handler(_save, events.NewMessage(chats=channel_ids))
    client.add_event_handler(_save, events.MessageEdited(chats=channel_ids))
