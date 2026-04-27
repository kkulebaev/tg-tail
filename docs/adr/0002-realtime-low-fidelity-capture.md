# 0002 — Realtime-only, low-fidelity capture

- Status: Accepted
- Date: 2026-04-27

## Context

A "Telegram archiver" can mean very different products depending on three orthogonal axes:

1. **Backfill scope** — capture only future posts vs. paginate channel history.
2. **Edit fidelity** — keep every revision as a separate row vs. overwrite in place.
3. **Delete fidelity** — soft-delete with timestamp vs. ignore (post lingers in DB after Telegram delete).

Maximal fidelity (full backfill, edit history table, soft-delete on `MessageDeleted`) is a substantially bigger system: extra tables, extra workers, and a large initial scrape that triggers Telegram flood-waits. The MVP user wants `tail -f` for a handful of channels they actively follow — closer to a notification log than to a forensic archive.

## Decision

Optimize for **low-fidelity, realtime-only** capture:

- **No historical backfill.** Telethon's `catch_up=True` covers short reconnects only. Anything older than the last disconnect is gone for our purposes.
- **Edits overwrite the row.** No `message_revisions` table. `MessageEdited` events update `text`, `entities`, `views`, `forwards`, `edit_date`, `raw`, `updated_at` on the existing row. Old text is lost.
- **Deletes are ignored.** No `MessageDeleted` handler. Posts removed from Telegram remain in the DB indefinitely.

The capture semantics are documented in the README under a "Capture semantics (intentional)" callout so users know what they're getting before they deploy.

## Consequences

- **Schema is simple.** One row per `(channel_id, message_id)`, enforced by a unique constraint. No history sub-tables, no tombstone columns.
- **Storage is bounded.** No edit accumulation, no historical scrape — disk grows at the channel's actual posting rate.
- **No flood-waits at startup.** Worker boots, subscribes, processes events as they arrive. Telegram doesn't see us scanning.
- **Outages create gaps.** A multi-hour worker outage means lost posts. There is no recovery story beyond the catch-up window.
- **The DB cannot answer "what did this post look like yesterday".** If that question matters later, it's a new ADR (and a migration to add a revisions table).
- **Forensic / audit use cases are out of scope.** The README explicitly steers those users elsewhere.

## Revisit when

- A user asks "where's the post from <date>" about a post they know existed but isn't in our DB → reconsider backfill.
- A user expresses surprise that an edit lost prior text → reconsider edit history.
- Compliance/legal reason to retain proof of deletion → reconsider delete tracking.
