# 0003 — Hybrid schema: typed columns + JSONB raw

- Status: Accepted
- Date: 2026-04-27

## Context

Telegram's `Message` object is large and Telethon-version-coupled. Two extremes for persisting it:

- **Pure JSONB** (one column, no schema) — fast to start, painful to query, no DB-level guarantees, schema drift is silent.
- **Pure typed columns** — every field gets a column. Strong queries, but every Telethon update or new message kind needs a migration, and any field we forgot to type is just lost.

Both are bad. The fields we actually query (channel, time, text, media status) are small in number and stable; the long tail of fields (forward headers, restricted geo, sticker metadata, replies-to header chain, etc.) is large and changes between Telethon releases.

## Decision

Use a **hybrid** schema:

- **Typed columns** for fields we filter or sort by (and for media-pipeline status):
  `channel_id`, `message_id`, `date`, `edit_date`, `text`, `entities` (JSONB but typed), `media_type`, `media_status`, `media_meta`, `media_storage_url`, `media_attempts`, `media_last_error`, `views`, `forwards`, `reply_to_msg_id`, `grouped_id`, `post_author`.
- **`raw` JSONB column** carrying the full `Message.to_dict()` output, scrubbed for JSON-safety (bytes → base64, datetime → ISO string).
- **Indexes on what we query**: `UNIQUE(channel_id, message_id)`, `(channel_id, date)`, partial index on `media_status WHERE status IN ('pending','failed')`.

## Consequences

- **No data loss from schema drift.** New Telegram fields land in `raw` automatically. We promote a field to a typed column only when we actually need to query it.
- **Indexed queries are cheap.** Per-channel chronology, dedupe, media-pipeline polling all hit indexes.
- **`raw` is large but bounded.** ~1–10 KB per row. Compression and TOAST handle it well in Postgres.
- **Edits update `raw` too.** Combined with ADR-0002, this means we never see the pre-edit `raw` again.
- **Promoting a JSONB field to a column requires a migration with a backfill.** That's expected and non-painful via Alembic + a `UPDATE ... SET col = raw->>'field'` step.
- **Type-strictness is at the application boundary, not the DB.** Telethon's `parse_message` decides what's authoritative. The DB stores what we hand it.
