# 0007 — Migrations run in container entrypoint

- Status: Accepted
- Date: 2026-04-27

## Context

Schema migrations have to run somewhere between "code merged" and "app handles traffic". Common patterns:

- **CI step before deploy** — fine for monorepos with explicit deploy gates, but Railway deploys are git-push-driven and don't expose a pre-start hook we can stage migrations against.
- **One-off operator command** — easy to forget; new schema deployed before migration run leaves the app crash-looping with confusing errors.
- **App-startup migration** — runs every container boot. Concern: race between concurrent containers running migrations.

We are running a **single replica** worker (one Telethon session, one event loop). There is no horizontal scaling on the cards — Telethon sessions don't share. So the race concern doesn't apply.

## Decision

`entrypoint.sh` runs `alembic upgrade head` before `exec python -m tg_tail`. The Dockerfile's `ENTRYPOINT` points at this script. Migrations are part of every container start.

`alembic/env.py` reads only `DATABASE_URL` from the environment (not the full `Settings`), so migrations can run even when Telegram or S3 secrets are missing — useful during partial bring-up and during initial provisioning.

## Consequences

- **Deploy and migrate are atomic.** A code change that needs new schema works on first boot. No drift window.
- **A bad migration crash-loops the worker** instead of just leaving the DB stale. That's the right failure mode — it's louder.
- **Migrations have to be idempotent and forward-only.** Alembic's `--head` flag handles the idempotency at the version-graph level; SQL DDL inside revision files is our responsibility.
- **No support for multi-replica deployment.** If we ever need that, this ADR is superseded — migrations move out of entrypoint and into a separate one-shot job.
- **`alembic/env.py` is decoupled from `Settings`.** Adding a required app-level env var doesn't break migrations. (See `src/tg_tail/config.py:normalize_database_url`.)
