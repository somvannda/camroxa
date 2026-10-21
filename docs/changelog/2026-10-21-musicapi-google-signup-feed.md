# Music web: Google signup notifications

**Branch:** `fix/musicapi-google-signup-feed`
**Date:** 2026-10-21

## Why

`music.camxora.com` onboarding runs through **musicapi**, not the platform API.
`POST /auth/google/callback` inserts straight into musicapi's own `users`
table, so the platform_api hook that wraps `UserRepository.create` never sees
the account. Result: Google signups on music web produced no `SIGNUP` message
in the shared ops channel, while platform (app/desktop) Google signups did.

Confirmed in production: a platform Google signup on 2026-10-21 wrote a
`kind='signup'` delivery row, while musicapi's recent Google users had no feed
entry.

## Changes

`musicapi/src/server.ts`

- `sendTelegram(text, { html })` now optionally sends `parse_mode: HTML`;
  existing alerts are unchanged (plain text).
- New `notifySignup(user, source)` posts the same shape as the platform feed:
  environment, escaped email/name, `status: FREE`, `product: music_web`,
  `source: google`, user id, Phnom Penh time.
- Called (fire-and-forget) only when the Google callback creates a **new**
  user; account links and sign-ins stay quiet.
- Production-only, like the existing alert sender.

## Tests

- `esbuild` transform of `musicapi/src/server.ts` — passed.
- `npm run typecheck` (`tsc --noEmit`) with the installed dependency tree —
  passed.

## Deploy

- No migration.
- Deploy `musicapi` (sandbox first), restart `camxora-musicapi`.
- Next new Google signup on music.camxora.com should appear as:
  `SIGNUP · Production / email: … / status: FREE / product: music_web / source: google`.
