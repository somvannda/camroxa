# Complete Cloudflare Turnstile Canonical Integration

**Date**: 2026-08-16
**Type**: Feature - Security Enhancement
**Impact**: Critical - Fixes bot protection for login/register

## Problem
Turnstile integration was incomplete and not following the canonical pattern from Cloudflare documentation. The backend only checked `success` but did not validate `action` or `hostname`, causing all verification attempts to fail.

## Solution
Implemented the complete canonical Turnstile integration flow as documented at developers.cloudflare.com/turnstile/spin:

### Frontend Changes
1. **Added `data-action` attributes** to Turnstile widgets:
   - Login widget: `data-action="login"`
   - Register widget: `data-action="register"`

### Backend Changes
1. **Updated `TurnstileService.verify()`** to return full Cloudflare response dict instead of just boolean
   - Returns: `{success, action, hostname, challenge_ts, error-codes}`

2. **Implemented canonical validation** in auth endpoints:
   - ✅ Validate `success === true`
   - ✅ Validate `action` matches expected ("login" or "register")
   - ✅ Validate `hostname` is in allowlist

3. **Added hostname configuration**:
   - New setting: `CLOUDFLARE_TURNSTILE_HOSTNAMES` (comma-separated list)
   - Sandbox: `music.sandbox.camxora.com,localhost,127.0.0.1`

### Technical Details
- Request format: `application/x-www-form-urlencoded` (via `data={}`)
- Siteverify endpoint: `https://challenges.cloudflare.com/turnstile/v0/siteverify`
- Site key: `0x4AAAAAAERrvCRyn8xcIet3`
- Actions: `login` and `register`

## Files Changed
- **Frontend**:
  - `music_web/src/app/login/page.tsx` - Added `data-action="login"`
  - `music_web/src/app/register/page.tsx` - Added `data-action="register"`

- **Backend**:
  - `platform_api/services/shared/turnstile_service.py` - Return full response dict
  - `platform_api/routers/auth.py` - Canonical validation (success + action + hostname)
  - `platform_api/config.py` - Added `cloudflare_turnstile_hostnames` setting
  - `.deploy/secrets.sandbox.env` - Added `CLOUDFLARE_TURNSTILE_HOSTNAMES`

## Testing
1. Complete Turnstile challenge on login/register
2. Backend validates all three requirements
3. Invalid action or hostname is rejected
4. Token replay is rejected

## References
- Cloudflare Turnstile Spin: developers.cloudflare.com/turnstile/spin/prompt.md
- Existing-widget flow: lines 158-285
- Canonical siteverify: lines 78-124
