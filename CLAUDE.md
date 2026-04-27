# CLAUDE.md

Working notes for Claude Code in this repo. Keep updates short — this file is loaded into every session.

## What this project is

A single-tenant `tail -f` for Telegram channels: a Telethon user-mode worker subscribes to channels, persists each post to Postgres (typed columns + JSONB `raw`), and asynchronously downloads media to S3-compatible storage. Deployed as a single worker service on Railway. Not a forensic archive — see [`docs/adr/0002`](docs/adr/0002-realtime-low-fidelity-capture.md).

## Decisions you should respect (links, not summaries)

- [`docs/adr/`](docs/adr/) — eight load-bearing decisions, each with a "Revisit when" trigger. **Read the relevant ADR before changing capture semantics, schema shape, the media pipeline, or the storage backend.** Don't unilaterally add edit history, soft-delete, backfill, or fallbacks for missing TG creds — those are explicit non-goals.
- [`docs/TODO.md`](docs/TODO.md) — open work, including TG-account-aging gate that blocks first real run.
- [`README.md`](README.md) — user-facing setup, deploy, schema overview.

## Layout cheat sheet

```
src/tg_tail/
  app.py            # asyncio entrypoint: client.start → resolve channels → register handlers → catch_up → spawn downloader → run_until_disconnected
  config.py         # pydantic-settings; normalize_database_url is reused by alembic/env.py
  db/
    models.py       # SQLAlchemy 2.0 ORM; MEDIA_STATUS_* constants live here
    repository.py   # all DB ops; upsert_message keys on uq_messages_channel_message
    engine.py
  tg/
    client.py       # StringSession wiring
    parser.py       # Message.to_dict() → scrubbed dict + parsed typed fields
    listener.py     # NewMessage + MessageEdited handlers (both call upsert_message)
  media/
    s3.py           # aioboto3 wrapper with path-style addressing (ADR-0008)
    downloader.py   # poll-claim-download loop; semaphore-bounded
alembic/             # env.py reads only DATABASE_URL (ADR-0007)
scripts/login.py     # one-time local TG_SESSION bootstrap
docker-compose.yml   # local Postgres + MinIO for parity
entrypoint.sh        # alembic upgrade head; exec python -m tg_tail
```

## Commands

```sh
# local stand
docker compose up -d                              # Postgres + MinIO
docker compose down -v                            # full cleanup

# dev loop
uv sync
uv run alembic upgrade head
uv run python -m tg_tail

# quality gates (CI runs the same; run all four before committing)
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest -q

# new migration (autogenerate, then edit by hand before committing)
DATABASE_URL=postgresql+asyncpg://tg_tail:tg_tail@localhost:5432/tg_tail \
  uv run alembic revision --autogenerate -m "description"

# Railway (CLI is project-linked; whoami should print the operator's email)
railway status
railway logs --service tg-tail
railway logs --service tg-tail --build
railway variable set --service tg-tail KEY=value
```

## Conventions

- **Conventional Commits.** `feat(scope):`, `fix(scope):`, `chore:`, `docs:`, `test:`, `ci:`. Atomic — one logical change per commit.
- **No emojis** in code, comments, or commit messages.
- **No comments unless the *why* is non-obvious.** Identifiers carry the *what*. The Dockerfile, ADRs, and PR descriptions carry the *why*.
- **Quality gates are mandatory before every commit.** ruff (lint + format), mypy `--strict`, pytest. CI re-runs them; surfacing a failure locally first is the cheap way.
- **Migrations are forward-only and idempotent at the version-graph level.** Alembic handles that — your job is to make the SQL inside each revision reversible (real `downgrade()`).
- **Secrets handling.** `TG_SESSION` is treated as a password (`SecretStr`). Never log raw `Settings()`. Never commit `.env`.
- **Channel IDs / usernames** are user-controlled strings — `parse_message` must reject anything that isn't a `PeerChannel`.
- **`raw` JSONB scrubbing** is `_scrub` in `tg/parser.py`. If you add a field to typed columns, also confirm `raw` still serializes (no `bytes` or naive `datetime` leaks).

## Gotchas worth flagging

- **Single-replica deployment.** Two workers would each grab the same Telethon session, which fights itself; the migrations-in-entrypoint pattern also assumes no race. If horizontal scale ever comes up, that's a new ADR.
- **`media_status='downloading'` orphans.** No reclamation pass exists yet — see TODO.md. Don't add one preemptively; wait for an actual orphan to appear in production.
- **`file_reference` expiry.** The downloader re-fetches the message via `client.get_messages` for a fresh reference. We never persist `file_reference`. Don't add a column for it.
- **Path-style S3.** Forced for all endpoints (`media/s3.py`). MinIO and Railway-issued domains require it; AWS tolerates it. Don't switch to virtual-host style without checking ADR-0008.
- **Alembic env decoupling.** `alembic/env.py` reads `DATABASE_URL` directly via `os.environ`, not through `Settings`. This is intentional — migrations must run before TG/S3 secrets are wired up. Don't "clean it up" by re-importing `Settings`.

## When working with libraries

If you're touching Telethon, SQLAlchemy, Alembic, pydantic-settings, aioboto3, structlog, or any cloud SDK — fetch current docs via Context7 (`resolve-library-id` → `query-docs`) before writing code. Training data drifts.

## Don't

- Don't add features beyond the bug fix or task at hand. No refactoring drive-bys, no helper extraction "while I'm here".
- Don't write fallback paths for missing required env vars. `Settings()` should fail loud and early.
- Don't introduce a job broker (Celery, RQ, Arq). The DB-backed state machine is the architecture (ADR-0004).
- Don't `git push --force` to `main`. Don't skip pre-commit hooks (`--no-verify`).
- Don't create extra docs (`*.md`, READMEs in subdirs) unless explicitly asked. Update existing ones.
