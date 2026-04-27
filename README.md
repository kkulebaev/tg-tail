<p align="center">
  <img src="docs/assets/banner.svg" alt="tg-tail — tail -f for Telegram channels" width="900">
</p>

<p align="center">
  <strong>Realtime archival of Telegram public-channel posts to PostgreSQL,</strong><br>
  with media offloaded to S3-compatible storage. One worker, one Postgres, one bucket.<br>
  Built for Railway, runs anywhere Docker does.
</p>

<p align="center">
  <a href="https://github.com/kkulebaev/tg-tail/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/kkulebaev/tg-tail/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="Type-checked: mypy --strict" src="https://img.shields.io/badge/types-mypy%20strict-1f5082">
  <a href="https://docs.astral.sh/ruff"><img alt="Linted with Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
  <a href="https://github.com/astral-sh/uv"><img alt="Built with uv" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json"></a>
  <a href="https://www.conventionalcommits.org"><img alt="Conventional Commits" src="https://img.shields.io/badge/conventional%20commits-1.0.0-fe5196"></a>
</p>

---

## Why

You follow a handful of Telegram channels, want everything they publish in your own database, and want media in your own bucket. You don't want a forensic archive, you don't want history backfill, and you don't want to run Celery and Redis to download a few files. This is a single-tenant `tail -f` for that specific shape of problem.

## What you get

- A Telethon **user-mode** worker that subscribes to your channels and persists every `NewMessage` and `MessageEdited`.
- A Postgres schema that's **typed where you'll query** (`channel_id`, `date`, `media_status`, indexes you'd expect) and **JSONB where you won't** (a `raw` column with the full Telethon payload, scrubbed for safe round-trip).
- An **async media downloader** driven by a DB-backed state machine (`pending → downloading → done | failed | skipped_too_large`) — concurrency-bounded, with retries and a per-file size cap. No broker.
- **Stateless container.** Auth is a `StringSession` env var, migrations run in `entrypoint.sh`, deployment is a single Railway service.
- **Local parity** via `docker-compose.yml` — Postgres + MinIO with one command.

## What this is *not*

- Not a forensic archive. Edits **overwrite**. Deletes are **ignored**. There is **no historical backfill**.
- Not a multi-tenant SaaS. One worker, one Telegram session, one Postgres.
- Not a Bot-API integration. Channel access mirrors a real user account's membership.

The semantics are deliberate — see [ADR-0002](docs/adr/0002-realtime-low-fidelity-capture.md) for the full reasoning and the conditions under which it's worth revisiting.

## Stack

`Python 3.12` · `Telethon` (MTProto user-mode) · `SQLAlchemy 2.0 async` + `asyncpg` · `Alembic` · `pydantic-settings` · `structlog` · `aioboto3` · `uv` · `Docker`.

Lint, format, typecheck, test gates: `ruff`, `mypy --strict`, `pytest` — all wired into `.github/workflows/ci.yml`.

## Quickstart

### 1. Telegram credentials

Create an app at <https://my.telegram.org> (API development tools). Note `api_id` and `api_hash`. The form requires the account to be ~2 weeks old before it'll mint credentials.

### 2. Generate a session string (one-time, locally)

```sh
cp .env.example .env
# fill TG_API_ID and TG_API_HASH

uv sync
uv run python scripts/login.py
# phone → code → optional 2FA
# copy the printed TG_SESSION=... line into .env (and Railway env later)
```

### 3. Join channels

In your Telegram client, under the **same account** whose session you just minted, join every channel you want to archive. The user must be a member for Telethon to receive messages.

### 4. Configure channels

```ini
CHANNEL_IDS=@durov,-1001234567890,@somepublicchannel
```

Comma-separated — numeric IDs or `@username`. They are resolved at startup and upserted into the `channels` table.

### 5. Deploy on Railway

```sh
railway link --project tg-tail              # or `railway init`
railway add --database postgres
railway add --image minio/minio:latest --service Storage
# in the Storage service: mount a volume on /data and set MINIO_ROOT_USER/MINIO_ROOT_PASSWORD
railway add --repo <your-fork>/tg-tail --service tg-tail

railway variable set --service tg-tail \
  'DATABASE_URL=${{Postgres.DATABASE_URL}}' \
  'S3_ENDPOINT_URL=${{Storage.MINIO_PRIVATE_ENDPOINT}}' \
  'S3_ACCESS_KEY_ID=${{Storage.MINIO_ROOT_USER}}' \
  'S3_SECRET_ACCESS_KEY=${{Storage.MINIO_ROOT_PASSWORD}}' \
  S3_BUCKET=tg-tail-media \
  TG_API_ID=... TG_API_HASH=... TG_SESSION='...' \
  CHANNEL_IDS=@channel1,@channel2
```

Migrations run on every container start via `entrypoint.sh`. Logs:

```sh
railway logs --service tg-tail
```

## Local development

```sh
docker compose up -d                   # Postgres + MinIO
uv sync
uv run alembic upgrade head
uv run python -m tg_tail
docker compose down -v                 # full cleanup
```

Defaults: Postgres `postgresql+asyncpg://tg_tail:tg_tail@localhost:5432/tg_tail`, MinIO API `http://localhost:9000`, MinIO Console `http://localhost:9001` (user `minio`, password `minio12345`).

Quality gates before committing:

```sh
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q
```

## Schema at a glance

```
channels
├── id            BIGINT PK     -- Telegram channel id
├── username      VARCHAR(255)
├── title         VARCHAR(255)
└── added_at      TIMESTAMPTZ

messages
├── id            BIGINT PK
├── channel_id    BIGINT FK → channels.id
├── message_id    BIGINT
├── date / edit_date / created_at / updated_at
├── text          TEXT
├── entities      JSONB
├── media_type    VARCHAR(32)
├── media_status  VARCHAR(32)        -- none | pending | downloading | done | failed | skipped_too_large
├── media_meta    JSONB
├── media_storage_url  TEXT          -- s3://bucket/YYYY/MM/DD/<channel_id>/<message_id>
├── media_attempts / media_last_error
├── views / forwards / reply_to_msg_id / grouped_id / post_author
└── raw           JSONB NOT NULL     -- full Telethon Message.to_dict(), bytes→base64, datetime→ISO

UNIQUE  (channel_id, message_id)
INDEX   (channel_id, date)
INDEX   (media_status) WHERE media_status IN ('pending', 'failed')
```

## Operational notes

- **`TG_SESSION` is the most sensitive secret** — full access to the user account. Treat as a password.
- **Schema changes** go through Alembic: `uv run alembic revision --autogenerate -m "..."`, edit by hand, commit, redeploy.
- **Failed media** (after `MEDIA_MAX_ATTEMPTS`) sit in `messages` with `media_status='failed'` and `media_last_error`. To retry: `UPDATE messages SET media_status='pending', media_attempts=0, media_last_error=NULL WHERE id = ...`.
- **Single-replica only.** Two workers would fight over the same Telethon session and race on migrations.

## Documentation

- [`docs/adr/`](docs/adr/) — eight Architecture Decision Records covering the load-bearing choices, each with a "Revisit when" section.
- [`docs/TODO.md`](docs/TODO.md) — open work, blocked items, planned follow-ups.
- [`CLAUDE.md`](CLAUDE.md) — context for Claude Code sessions; doubles as a contributor cheat sheet.

## Tuning knobs

| Variable | Default | Effect |
|---|---|---|
| `MEDIA_CONCURRENCY` | `3` | Parallel media downloads. |
| `MEDIA_POLL_INTERVAL_SECONDS` | `5` | Idle poll cadence when the queue is empty. |
| `MEDIA_MAX_ATTEMPTS` | `5` | After this, the row goes to `failed`. |
| `MEDIA_MAX_BYTES` | `100 MB` | Files larger than this are stored as `skipped_too_large` (metadata only). |
| `LOG_LEVEL` | `INFO` | structlog level. |
| `LOG_FORMAT` | `json` | `json` for prod, `console` for local pretty-printing. |
