# Music portal login lockout — wrong Turnstile sitekey in the production build

**Date:** 2026-10-05
**Branch:** `fix/music-web-turnstile-sitekey`
**Surfaces:** music_web, platform_api (env only), scripts/deploy
**Status:** production hotfix applied; hardening implemented (not yet merged)

## Summary

Users could not log in at `music.camxora.com`: pressing **Sign in** did nothing.
The Turnstile widget showed Cloudflare's **"Unable to connect to website"**
error where the challenge should render.

Root cause: the production `music_web` build shipped the **sandbox** Turnstile
sitekey (`0x4AAAAAAERrvCRyn8xcIet3`). `TurnstileWidget` silently fell back to
that key whenever `NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY` was unset at build
time. Cloudflare rejects a sitekey that is not allowed for the requesting
hostname, so the widget errored, never produced a token, and the login form
stayed disabled:

```tsx
// music_web/src/app/login/page.tsx
disabled={busy || !turnstileToken}
```

The API, database, and credentials were all fine — `/api/v3/health` was 200 and
login with bad credentials returned the expected `401`.

## Product impact

- Login and sign-up work again at `music.camxora.com` (Turnstile issues a token
  in ~1.5s and the button enables).
- A production build that is missing the Turnstile sitekey now shows an explicit
  "Security check is unavailable" message instead of a broken widget that
  silently blocks every user.

## Technical impact

- `music_web/src/components/turnstile-widget.tsx`: resolve the sitekey once at
  module scope. The sandbox key is used **only** when
  `process.env.NODE_ENV === 'development'`; in production a missing key renders a
  visible `role="alert"` error and skips `turnstile.render`.
- `music_web/src/lib/turnstile-sitekey.ts`: pure `resolveTurnstileSiteKey()` /
  `isSandboxTurnstileSiteKey()` extracted so the no-fallback rule is unit tested
  and reusable.
- `music_web/scripts/check-turnstile-sitekey.mjs`: `prebuild` guard that refuses a
  production build (`NEXT_PUBLIC_CAMXORA_ENV=production`) with a missing or sandbox
  sitekey. Local builds are unaffected.
- `scripts/deploy/apply_turnstile_production.py`: `sys.stdout.reconfigure(...)`
  to UTF-8 and print decoded remote output directly. The previous
  `print(out.encode("utf-8").decode("utf-8"))` raised `UnicodeEncodeError` on a
  cp1252 console **after** the remote work had succeeded, returning a false
  failure.
- `scripts/deploy/{sync_music_web_production,restore_production_api_turnstile_env_rollback,backfill_web_music_durations}.py`:
  same cp1252 fix.
- Production `platform_api/.env` was rewritten with the production Turnstile
  sitekey / secret / hostnames and `camxora-api` restarted.

## Files touched

- `music_web/src/components/turnstile-widget.tsx`
- `music_web/src/lib/turnstile-sitekey.ts`
- `music_web/src/lib/turnstile-sitekey.test.ts`
- `music_web/scripts/check-turnstile-sitekey.mjs`
- `music_web/package.json`
- `scripts/deploy/apply_turnstile_production.py`
- `scripts/deploy/sync_music_web_production.py`
- `scripts/deploy/restore_production_api_turnstile_env_rollback.py`
- `scripts/deploy/backfill_web_music_durations.py`

## Migration / deploy

- No schema migration.
- Hotfix (already applied to production on 2026-10-05):
  `python scripts/deploy/apply_turnstile_production.py --rebuild-music-web`.
  This updates `platform_api/.env` (sitekey/secret/hostnames), restarts
  `camxora-api`, rebuilds `music_web`, and restarts `camxora-music`.
- The sitekey is baked in at build time, so **`music_web` must be rebuilt** —
  setting the env var alone is not enough.

## Tests

- Verified live: `/api/v3/health` 200; login with bad credentials 401; live
  `/login` bundle contains the production sitekey; in a browser the Turnstile
  frame no longer shows the error and issues an 837-char token, enabling the
  button.
- `python -m py_compile` on all four deploy scripts.
- `music_web`: `npm test`
  (`node --experimental-strip-types --test "src/lib/*.test.ts"`) — **49 passed**,
  including 7 new `turnstile-sitekey` cases covering the no-fallback regression.
- `prebuild` guard exercised directly: no env → pass; production + missing key →
  fail; production + sandbox key → fail; production + real key → pass.

## Follow-ups

- Optional post-build assertion that the compiled `.next` chunks contain the
  expected sitekey, as defence against a build-cache or env-precedence surprise.

