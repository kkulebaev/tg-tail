from telethon import TelegramClient
from telethon.sessions import StringSession


def make_client(api_id: int, api_hash: str, session: str) -> TelegramClient:
    return TelegramClient(StringSession(session), api_id, api_hash)
