# 0006 — Telethon StringSession via environment variable

- Status: Accepted
- Date: 2026-04-27

## Context

Telethon stores its authenticated session (auth keys, DC routing, message-id mappings) somewhere. The default is a local SQLite file (`<name>.session`). On Railway containers, the filesystem is ephemeral — every restart wipes it, and every restart would prompt for a fresh phone-code login that no human is around to enter.

Telethon ships a `StringSession` variant that serializes the same state into a string we can stash anywhere — including an environment variable.

## Decision

Authenticate once locally via `scripts/login.py`, which prints a `TG_SESSION=<long string>` line. The operator copies this into Railway as a regular env var. The application loads it via `StringSession(settings.tg_session.get_secret_value())` at startup.

## Consequences

- **No persistent disk required.** The container is fully stateless from the Telegram-auth perspective.
- **Restart is free.** New container boots, reads `TG_SESSION`, and is logged in immediately.
- **`TG_SESSION` is the most sensitive secret in the system.** It grants full access to the user account — DMs, contacts, the lot. Treated as `SecretStr` in code and stored as a Railway env var (encrypted at rest). README calls this out under "Operational notes".
- **Bootstrap requires interactivity.** Phone code, optional 2FA — only the human operator can do this. `scripts/login.py` runs locally; output is then pasted into Railway.
- **Session strings can theoretically expire** if Telegram invalidates the auth_key (account locked, server-side reset). Recovery is rerunning the bootstrap. We don't try to detect this proactively; the worker will surface auth errors in logs.
