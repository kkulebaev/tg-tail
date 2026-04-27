import base64
from datetime import date, datetime
from typing import Any

from telethon.tl.types import (
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerChannel,
)


def _scrub(obj: Any) -> Any:
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_scrub(v) for v in obj]
    return obj


def _media_type(media: Any) -> str | None:
    if media is None:
        return None
    if isinstance(media, MessageMediaPhoto):
        return "photo"
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        attributes = getattr(doc, "attributes", None) or []
        for attr in attributes:
            name = type(attr).__name__
            if name == "DocumentAttributeVideo":
                return "video"
            if name == "DocumentAttributeAudio":
                return "voice" if getattr(attr, "voice", False) else "audio"
            if name == "DocumentAttributeAnimated":
                return "gif"
            if name == "DocumentAttributeSticker":
                return "sticker"
        return "document"
    return type(media).__name__.lower().replace("messagemedia", "")


def _media_size_bytes(media: Any) -> int | None:
    if isinstance(media, MessageMediaPhoto):
        photo = getattr(media, "photo", None)
        sizes = getattr(photo, "sizes", None) or []
        candidates = [int(getattr(s, "size", 0) or 0) for s in sizes]
        return max(candidates) if candidates else None
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        size = getattr(doc, "size", None)
        return int(size) if size is not None else None
    return None


def parse_message(msg: Message) -> dict[str, Any]:
    """Convert a Telethon Message to a dict suitable for the messages table.

    Returns None for `channel_id` if the message is not from a channel — caller
    should filter those out before calling.
    """
    peer = msg.peer_id
    if not isinstance(peer, PeerChannel):
        raise ValueError(f"Message {msg.id} is not from a channel: {type(peer).__name__}")
    channel_id = int(peer.channel_id)

    media = getattr(msg, "media", None)
    media_type = _media_type(media)
    has_media = media_type is not None

    raw = _scrub(msg.to_dict())

    entities_raw = msg.entities
    entities = _scrub([e.to_dict() for e in entities_raw]) if entities_raw else None

    media_meta: dict[str, Any] | None = None
    if has_media:
        size = _media_size_bytes(media)
        media_meta = {
            "size_bytes": size,
            "tl": _scrub(media.to_dict()) if media is not None else None,
        }

    reply_to_msg_id: int | None = None
    if msg.reply_to is not None:
        reply_to_msg_id = getattr(msg.reply_to, "reply_to_msg_id", None)

    return {
        "channel_id": channel_id,
        "message_id": int(msg.id),
        "date": msg.date,
        "edit_date": msg.edit_date,
        "text": msg.message or None,
        "entities": entities,
        "media_type": media_type,
        "media_meta": media_meta,
        "views": msg.views,
        "forwards": msg.forwards,
        "reply_to_msg_id": reply_to_msg_id,
        "grouped_id": int(msg.grouped_id) if msg.grouped_id else None,
        "post_author": getattr(msg, "post_author", None),
        "raw": raw,
        "_has_media": has_media,
        "_media_size_bytes": _media_size_bytes(media) if has_media else None,
    }
