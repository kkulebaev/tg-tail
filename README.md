# tg-tail

`tail -f` for Telegram channels — archives posts to PostgreSQL via a user account.

## What it does

- Listens to `NewMessage` and `MessageEdited` events from a configured set of channels using a Telegram **user account** (Telethon, MTProto).
- Persists each post to PostgreSQL.
- Downloads media to MinIO (any S3-compatible storage) asynchronously, with retry and a per-file size cap.
- Designed as a single worker service on Railway.

## Capture semantics (intentional)

- **Realtime only.** No historical backfill. `catch_up=True` covers short Telethon disconnects only — longer outages produce gaps.
- **Edits overwrite the row.** No edit history is kept.
- **Deletes are ignored.** Posts removed from Telegram remain in the database.
- **Media larger than `MEDIA_MAX_BYTES` (default 100 MB)** are recorded with status `skipped_too_large` — metadata stored, bytes not.

If you need a forensic archive (preserve every edit, capture deletes, full historical backfill), this project is not it.

## Stack

Python 3.12 · Telethon · SQLAlchemy 2.0 async + asyncpg · Alembic · pydantic-settings · structlog · aioboto3 · uv · Docker.

## Setup

### 1. Telegram credentials

Create an app at <https://my.telegram.org> → API development tools. Note `api_id` and `api_hash`.

### 2. Generate a session string (one-time, locally)

```sh
cp .env.example .env
# fill in TG_API_ID and TG_API_HASH

uv sync
uv run python scripts/login.py
# follow prompts: phone, code, optional 2FA
# copy the printed TG_SESSION=... line into your .env (and Railway env)
```

### 3. Join channels manually

In your Telegram client, under the **same account** whose session you generated, join every channel you want to archive. The user must be a member for Telethon to receive its messages.

### 4. Configure channels

```
CHANNEL_IDS=@durov,-1001234567890,@somepublicchannel
```

Comma-separated — each entry is either a numeric channel ID or `@username`. They are resolved at startup and upserted into the `channels` table.

### 5. Deploy on Railway

- New service from this repo (Dockerfile build is auto-detected).
- Add the **PostgreSQL** plugin → `DATABASE_URL` is injected automatically.
- Add a **MinIO** service (Docker template) and set:
  - `S3_ENDPOINT_URL` (internal URL of your MinIO service)
  - `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`
  - `S3_BUCKET` (will be auto-created on first run)
- Set Telegram secrets: `TG_API_ID`, `TG_API_HASH`, `TG_SESSION`.
- Set `CHANNEL_IDS`.
- Deploy. Migrations run on every container start via `entrypoint.sh`.

## Local development

```sh
uv sync
uv run alembic upgrade head
uv run python -m tg_tail
```

You'll need a local Postgres and MinIO (the easiest path is `docker run` for both, or a local `docker-compose.yml` you maintain outside this repo).

## Database schema

- `channels` — id (Telegram channel id), username, title, added_at.
- `messages` — typed columns for the fields we query (channel_id, message_id, date, text, media_type, media_status, etc.) plus `raw JSONB` carrying the full Telethon `Message.to_dict()` for anything we forgot to type. Unique on `(channel_id, message_id)`.

## Operational notes

- `TG_SESSION` is the most sensitive secret: it grants full access to the user account. Treat as a password.
- Schema changes go through Alembic — `uv run alembic revision --autogenerate -m "..."` to draft, edit, commit, redeploy.
- Failed media downloads (after `MEDIA_MAX_ATTEMPTS`) sit in `messages` with `media_status='failed'` and `media_last_error`. Reset to `'pending'` manually to retry.
