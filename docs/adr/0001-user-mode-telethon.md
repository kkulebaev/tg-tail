# 0001 — User-mode Telethon over Bot API

- Status: Accepted
- Date: 2026-04-27

## Context

We need to read posts from public Telegram channels and persist them. Telegram offers two surfaces for this:

- **Bot API** — official, easy to use, but a bot can only read messages in groups/channels where it's been added as a member with explicit privileges. Public broadcast channels rarely add bots.
- **MTProto user API** — same protocol the official Telegram clients use. A user account can read any channel it has joined, including public ones, by simply joining as a member.

Our product is a personal-scale archiver of channels the operator already follows. Joining channels as a regular user is the natural model.

## Decision

Use **Telethon** (Python MTProto client) authenticated as a user account. Bot API is excluded.

## Consequences

- The user account is the only authentication boundary. Anyone with `TG_SESSION` controls that account fully — treat it like a password.
- Channel access mirrors the user's membership: to add a channel to capture, the operator joins it in the Telegram client. No invite-bot dance.
- Telegram's anti-abuse heuristics target user sessions more aggressively than bots. Burst-y reads (large `get_history`, rapid joins) can trigger flood-waits or temporary account locks. Our usage pattern is event-driven and low-volume, which keeps us well below those thresholds.
- We give up Bot API features that don't exist in MTProto user-mode (e.g., inline keyboards as the bot author). Not relevant to this project.
- Onboarding requires a one-time interactive login (phone + code + optional 2FA) to mint a session string. Codified in `scripts/login.py`.
