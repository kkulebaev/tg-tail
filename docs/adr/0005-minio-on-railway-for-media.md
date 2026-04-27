# 0005 — MinIO on Railway for media storage

- Status: Accepted
- Date: 2026-04-27

## Context

Media bytes need an object store. Telegram's CDN refs are short-lived, the Postgres TOAST budget is the wrong place for large blobs, and serving them from worker disk doesn't survive container restarts. The DB is the index, not the bytes.

Candidates:

- **AWS S3** — gold standard, but billing requires a card, and we want zero-config dev parity.
- **Cloudflare R2** — S3-compatible, generous free tier, no egress fees. The pragmatic recommendation.
- **MinIO on Railway** — S3-compatible, runs as a service in the same project as the worker, single bill, fully self-contained.

The deciding factor was: this project is being deployed on Railway with no other infra. Keeping everything in one platform (one billing surface, one network, one ops dashboard) outweighs the small per-GB cost premium of running our own MinIO. R2 is a fine alternative and our code change to switch is just three env vars.

## Decision

Deploy **MinIO via the Railway template** (`Storage` service), with a persistent volume mounted at `/data`. The application speaks S3 to MinIO via `aioboto3`, addressed through `storage.railway.internal:9000` (Railway's private network). The bucket is created at app startup by `S3Client.ensure_bucket()`.

Storage credentials and endpoint are template-referenced from the `Storage` service:
`S3_ENDPOINT_URL=${{Storage.MINIO_PRIVATE_ENDPOINT}}`, `S3_ACCESS_KEY_ID=${{Storage.MINIO_ROOT_USER}}`, `S3_SECRET_ACCESS_KEY=${{Storage.MINIO_ROOT_PASSWORD}}`.

## Consequences

- **One platform, one bill.** No second vendor to manage.
- **Dev–prod parity.** `docker-compose.yml` runs the same MinIO image locally; only endpoint/keys differ.
- **We own the durability story.** Railway volumes are single-replica; a region outage takes the data with it. The capture is recoverable in principle (Telegram still has the originals) but the rebuild is not free. Acceptable for the use case but not for archival-grade media.
- **MinIO management is on us.** Bucket lifecycle, IAM, version upgrades, OOM tuning. Compared to R2, that's real work.
- **The S3 API is private** (`storage.railway.internal:9000`); only the MinIO Console is exposed publicly. Bucket admin from outside Railway requires the Console UI.
- **Storage credentials live in env vars on the Storage service.** Wiping the volume re-bootstraps IAM from those env vars; rotating them requires updating both `Storage` and the template references on `tg-tail`.

## Revisit when

- Monthly Railway storage charges exceed an R2-equivalent quote by a noticeable margin.
- We need cross-region durability or signed-URL distribution at scale.
- MinIO requires manual ops attention more than once per quarter.
