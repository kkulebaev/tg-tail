import asyncio
import contextlib

import structlog

from .config import get_settings
from .db.engine import make_engine, make_session_factory
from .logging import configure_logging
from .media.downloader import run_downloader
from .media.s3 import S3Client
from .tg.client import make_client
from .tg.listener import register_handlers, resolve_and_upsert_channels

log = structlog.get_logger(__name__)


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    log.info("starting", channel_count=len(settings.channel_ids))

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    s3 = S3Client(
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region=settings.s3_region,
        bucket=settings.s3_bucket,
    )
    await s3.ensure_bucket()

    client = make_client(
        settings.tg_api_id,
        settings.tg_api_hash.get_secret_value(),
        settings.tg_session.get_secret_value(),
    )

    await client.start()
    me = await client.get_me()
    log.info("telegram_connected", user_id=getattr(me, "id", None))

    if not settings.channel_ids:
        log.error("no_channels_configured")
        await client.disconnect()
        await engine.dispose()
        return

    resolved = await resolve_and_upsert_channels(client, session_factory, settings.channel_ids)
    if not resolved:
        log.error("no_channels_resolved")
        await client.disconnect()
        await engine.dispose()
        return

    register_handlers(client, session_factory, resolved, settings.media_max_bytes)

    await client.catch_up()
    log.info("listener_ready", channels=resolved)

    downloader_task = asyncio.create_task(
        run_downloader(
            client=client,
            s3=s3,
            session_factory=session_factory,
            concurrency=settings.media_concurrency,
            poll_interval_seconds=settings.media_poll_interval_seconds,
            max_attempts=settings.media_max_attempts,
        ),
        name="downloader",
    )

    try:
        await client.run_until_disconnected()
    finally:
        downloader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await downloader_task
        await client.disconnect()
        await engine.dispose()


def run() -> None:
    asyncio.run(_run())
