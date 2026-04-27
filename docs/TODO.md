# Open work

## Blocked on external

- **Telegram credentials.** `TG_API_ID` / `TG_API_HASH` cannot be provisioned at <https://my.telegram.org> until the user account is at least ~2 weeks old (the form returns a generic "ERROR" before then). When that lifts:
  1. Fill `TG_API_ID` and `TG_API_HASH` in local `.env`.
  2. Run `uv run python scripts/login.py`. Phone, code, optional 2FA → emits `TG_SESSION=<long string>`.
  3. Push secrets to Railway:
     ```sh
     railway variable set --service tg-tail \
       TG_API_ID=<id> \
       TG_API_HASH=<hash> \
       TG_SESSION='<session>' \
       CHANNEL_IDS=@channel1,@channel2
     ```
  4. Verify with `railway logs --service tg-tail`. First success looks like `downloader_started` followed by `media_downloaded` events as the channels post.

- **First media write creates the bucket** (`tg-tail-media`). Until then, the `Storage` MinIO instance has no bucket — that's expected and `S3Client.ensure_bucket()` handles it on first run. No action required.

## Optional polish

- **`Makefile` / `justfile`** for the recurring local commands (`uv run alembic upgrade head`, `uv run python -m tg_tail`, `uv run ruff check && uv run mypy && uv run pytest`, `docker compose up -d / down -v`). Low value when the commands are short, but reduces a small bit of friction.
- **README badges** for CI status and license once the workflow has run on a real PR.
- **Sentry / error tracking.** Deferred per [ADR-0002 spirit](adr/0002-realtime-low-fidelity-capture.md) — the worker logs structured errors to stdout, that's enough for personal-scale operation. Revisit when an outage actually goes unnoticed.

## Known follow-ups (revisit triggers from ADRs)

- **Stale `media_status='downloading'` reclamation.** Per [ADR-0004](adr/0004-db-state-machine-for-media-downloads.md): if a worker crashes mid-download, the row stays `downloading` forever. Add a startup pass that flips `downloading` → `pending` if `updated_at` is older than ~5 minutes, **once we observe orphans in practice**. Not premature — there is no auto-recovery today.
- **Edit history / delete tracking.** Per [ADR-0002](adr/0002-realtime-low-fidelity-capture.md): if anyone (including future-you) is surprised that `MessageEdited` overwrites or that deletes are silent, that's the trigger to write a follow-up ADR and add a revisions table or soft-delete column.
- **Object-storage durability.** Per [ADR-0005](adr/0005-minio-on-railway-for-media.md): Railway volumes are single-replica. If the project outgrows "one tenant, one region", the storage backend gets revisited (R2 + lifecycle policy, or AWS S3 with versioning).
- **LISTEN/NOTIFY for the media queue.** Per [ADR-0004](adr/0004-db-state-machine-for-media-downloads.md): the polling loop is fine at low volume. If `MEDIA_POLL_INTERVAL_SECONDS` ever needs to drop below 1s to keep up, switch the listener to push instead of poll.

## Done (for context)

- Single Railway project `tg-tail` with `Postgres`, `Storage` (MinIO), and the `tg-tail` app service. `Storage CLI` bootstrap helper deleted as redundant.
- Local dev stand (`docker-compose.yml`) for parity with prod backends.
- Alembic migrations decoupled from app `Settings` (env.py reads only `DATABASE_URL`).
- Path-style S3 addressing forced for non-AWS endpoints.
- README sections: capture semantics, setup, schema, operational notes.
- CI on every push and PR (`ruff`, `mypy --strict`, `pytest`).
