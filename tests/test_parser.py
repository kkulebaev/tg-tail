import json
from datetime import UTC, datetime
from typing import Any

import pytest
from telethon.tl.types import Message, PeerChannel, PeerUser

from tg_tail.tg.parser import parse_message


def _make_msg(**kwargs: Any) -> Message:
    defaults: dict[str, Any] = {
        "id": 42,
        "peer_id": PeerChannel(channel_id=1234567890),
        "date": datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        "message": "hello world",
    }
    defaults.update(kwargs)
    return Message(**defaults)


def test_parse_text_only_message() -> None:
    msg = _make_msg()
    result = parse_message(msg)

    assert result["channel_id"] == 1234567890
    assert result["message_id"] == 42
    assert result["text"] == "hello world"
    assert result["media_type"] is None
    assert result["_has_media"] is False
    assert result["_media_size_bytes"] is None
    assert isinstance(result["raw"], dict)


def test_parse_rejects_non_channel_message() -> None:
    msg = _make_msg(peer_id=PeerUser(user_id=1))
    with pytest.raises(ValueError, match="not from a channel"):
        parse_message(msg)


def test_raw_is_json_safe() -> None:
    """The raw dict must serialise cleanly through json.dumps for asyncpg→JSONB."""
    msg = _make_msg()
    result = parse_message(msg)
    json.dumps(result["raw"])


def test_empty_text_normalises_to_none() -> None:
    msg = _make_msg(message="")
    result = parse_message(msg)
    assert result["text"] is None


def test_grouped_id_passthrough() -> None:
    msg = _make_msg(grouped_id=999)
    result = parse_message(msg)
    assert result["grouped_id"] == 999
