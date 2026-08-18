# Music web KH-only geo + timed generation freeze

**Date:** 2026-08-18  
**Surfaces:** platform_api, music_web, admin_portal, nginx  
**Branch:** `feature/music-web-geo-gen-freeze`

## Summary

Music web is Cambodia-only at the API (Cloudflare `CF-IPCountry` must be `KH`). Attack-like generate/auth patterns auto-freeze music generation for 6 hours (user + IP). Admins can freeze 1 / 6 / 24 / 72 hours or unfreeze. Desktop studio, admin, and user portal are unchanged.

## Product impact

- Visitors outside Cambodia, Tor (`T1`), unknown country (`XX`), or missing Cloudflare country header cannot use `music.camxora.com` / `music.sandbox.camxora.com` or `/api/v1/web-music/*`.
- After an attack signal, Create is paused with a clear “try again in N hours” message. Browse/listen still work for that account unless they are geo-blocked.
- Admin user detail: **Freeze Generation** / **Unfreeze Generation** next to Suspend.

## What counts as an attack (auto 6h freeze)

| Signal | Threshold |
|---|---|
| Generate 429 storm | 8 hits on `/web-music/generate*` in 2 minutes |
| Quota hammer | 10 generate attempts after quota exceeded in 10 minutes |
| Login lockout | 5 failed passwords (existing 15 min login lock) also freezes generate |
| Signup farm | Same as shipped caps: 3 accounts/hour and 5/day per IP still 429. Freeze generate for that IP as an extra, not a new 8-account rule. |
| Payload probes | SQL / path-traversal / XSS fragments in generate lyrics/style/title |
| Polish probe storm | Existing daily probe threshold also freezes that user |

Not an attack: one double-click 429, 1–4 wrong passwords, running out of free credits once, Suno content-policy lyrics.

## Unchanged — signup farm protection (2026-08-18)

The earlier ship stays in force. Freeze is extra after those caps fire:

- Turnstile required on music-web register
- **3 successful accounts per IP per hour** (`MAX_ACCOUNTS_PER_IP_PER_HOUR`)
- **5 successful accounts per IP per day** (`MAX_ACCOUNTS_PER_IP_PER_DAY`)
- **5 free songs per IP per day**
- Register **attempts** still rate-limited at **8/hour per IP** (`REGISTER_RATE_LIMIT`) — that is not 8 successful accounts

The attack-freeze plan’s “8+ successful registers” line was **not** implemented as a cap and must not loosen 3/hour.

## Technical impact

- `MusicWebGeoMiddleware` on sandbox/production. Direct origin with no Cloudflare headers is allowed (sandbox DNS-only). Behind Cloudflare: missing/unknown/Tor/non-KH is blocked.
- Nginx forwards `CF-IPCountry` and `CF-Connecting-IP`.
- Redis keys `musicweb:genfreeze:user:{id}` and `musicweb:genfreeze:ip:{ip}`.
- Errors: `403 GEO_BLOCKED`, `403 GENERATION_FROZEN` (`retry_after` seconds in details).

## Files touched

- `platform_api/middleware/geo_access.py` (new)
- `platform_api/services/generation_freeze.py` (new)
- `platform_api/middleware/abuse_detection.py`, `rate_limit.py`, `auth.py` login lockout, `web_music.py`, `users.py`, `main.py`, `config.py`, `exceptions.py`, `abuse_alert_service.py`
- `scripts/deploy/nginx-camxora-sandbox.conf`, `nginx-camxora-production.conf`
- `admin_portal` user detail freeze UI
- `music_web` login/register/create error messages
- Tests: `test_geo_access.py`, `test_generation_freeze.py`

## Migration/deploy

No database migration.

Sandbox:

```bash
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/apply_nginx.py --env sandbox
python scripts/deploy/sync_admin_portal_sandbox.py
python scripts/deploy/rebuild_music_web_sandbox.py
```

Confirm sandbox `PLATFORM_ENVIRONMENT` is `staging` or `sandbox` (geo auto-on). Override with `PLATFORM_MUSIC_WEB_GEO_ENFORCE=true` if needed.

**Cloudflare dashboard (required, not in git):** WAF custom rule on `music.camxora.com` and `music.sandbox.camxora.com`: *Country is not KH → Block*. Enable Bot Fight / Block known anonymizers if the zone plan includes it. VPN with a Cambodian exit still looks like KH.

## Follow-up — play kicked to login (same day)

Sandbox play was sending logged-in users to `/login` and audio did not start. Causes:

- Geo middleware was `BaseHTTPMiddleware`, which can wrap/break Range audio on the music host.
- Create/public clip URLs `/stream/ok` and `/stream/alt` were not treated as trusted, so the player treated play as a failed catalog lookup and redirected to login.
- Unconfirmed music-web accounts could load `/users/me` but were forbidden on play/stream.

Fixes: pure ASGI geo gate; trust path-variant stream URLs; allow GET play/stream before email confirm; play-url uses cookie refresh; do not redirect to login when a session already exists.

Production only on request.

## Tests

- Geo: KH allowed; US / T1 / missing header denied; `api.camxora.com/web-music` denied; `/generation/suno` not geo-checked; `/health` exempt.
- Freeze: below threshold allowed; 8× generate 429 freezes user+IP; unfreeze clears; TTL expiry unfreezes.

## Follow-ups

- Production Cloudflare WAF KH-only rule.
- Paid IP-intel only if residential-VPN false negatives become a problem.
