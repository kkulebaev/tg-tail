# 0004 — DB-backed state machine for media downloads

- Status: Accepted
- Date: 2026-04-27

## Context

Media downloads are independent from message ingestion: text lands in milliseconds, but a 50 MB video may take seconds, fail on a stale `file_reference`, hit Telegram flood-waits, or exceed our size cap. We don't want media work blocking the listener loop, and we want to retry transient failures without re-triggering them on every reconnect.

Three options:

1. **In-process queue** (`asyncio.Queue` with consumer tasks) — simplest but loses queued items on restart; no operator visibility.
2. **External job queue** (Celery / RQ / Arq + Redis) — robust, but adds a broker, a worker pool, and out-of-band ops. Overkill for a single-tenant archiver.
3. **DB-backed state machine** — the `messages` row itself carries `media_status` (`none`/`pending`/`downloading`/`done`/`failed`/`skipped_too_large`), `media_attempts`, and `media_last_error`.

## Decision

Option 3. The downloader is an `asyncio` coroutine that polls Postgres for `media_status='pending'`, claims rows by setting `downloading`, runs the download, and writes the terminal status back. A partial index on `media_status` keeps the poll cheap.

Concurrency is controlled by `MEDIA_CONCURRENCY` (semaphore) and `MEDIA_POLL_INTERVAL_SECONDS`. Retry budget is `MEDIA_MAX_ATTEMPTS`; on each failure the row goes back to `pending` until the budget is exhausted, then it transitions to `failed` with the truncated error message stored.

## Consequences

- **No broker.** One Postgres, one worker. Matches the rest of the architecture.
- **Crash-safe retry.** If the worker dies mid-download, the row remains `downloading`. (Trade-off: we don't currently reclaim stale `downloading` rows on startup — that's a planned follow-up if we observe orphans in practice.)
- **Operators have a real handle on the pipeline.** `SELECT media_status, count(*) FROM messages GROUP BY 1` is the dashboard.
- **Manual replay is trivial.** Reset a row: `UPDATE messages SET media_status='pending', media_attempts=0, media_last_error=NULL WHERE id = ...`.
- **`file_reference` can expire while a row sits pending**, so the downloader re-fetches the message via `client.get_messages(channel_id, ids=message_id)` to get a fresh reference; we never persist `file_reference` itself.
- **Polling is wasted work when the queue is empty.** Acceptable at our scale; the partial index makes "no work to do" cheap. If channel volume grows materially, switch to LISTEN/NOTIFY.
