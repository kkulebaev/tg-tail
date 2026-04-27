# Architecture Decision Records

Each ADR captures one non-obvious architectural choice: the constraint, the chosen path, and the trade-off being accepted. Format: lightweight [Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). Records are immutable — to revisit a decision, write a new ADR that supersedes the old one.

| # | Title | Status |
|---|---|---|
| [0001](0001-user-mode-telethon.md) | User-mode Telethon over Bot API | Accepted |
| [0002](0002-realtime-low-fidelity-capture.md) | Realtime-only, low-fidelity capture | Accepted |
| [0003](0003-hybrid-typed-columns-and-jsonb.md) | Hybrid schema: typed columns + JSONB raw | Accepted |
| [0004](0004-db-state-machine-for-media-downloads.md) | DB-backed state machine for media downloads | Accepted |
| [0005](0005-minio-on-railway-for-media.md) | MinIO on Railway for media storage | Accepted |
| [0006](0006-string-session-via-env.md) | Telethon StringSession via environment variable | Accepted |
| [0007](0007-migrations-in-entrypoint.md) | Migrations run in container entrypoint | Accepted |
| [0008](0008-path-style-s3-addressing.md) | Path-style S3 addressing | Accepted |
