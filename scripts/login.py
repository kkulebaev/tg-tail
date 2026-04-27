"""One-shot interactive login. Generates TG_SESSION for env.

Usage:
    cp .env.example .env
    # fill in TG_API_ID and TG_API_HASH
    uv run python scripts/login.py
    # follow prompts, copy printed value into Railway env as TG_SESSION
"""

import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    load_dotenv()
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = await client.get_me()
        print(f"\nLogged in as: {me.username or me.first_name} (id={me.id})")
        print("\nCopy the line below into your Railway env:\n")
        print(f"TG_SESSION={client.session.save()}")


if __name__ == "__main__":
    asyncio.run(main())
