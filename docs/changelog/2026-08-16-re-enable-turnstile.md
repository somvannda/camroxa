# Re-enable Cloudflare Turnstile Bot Protection

**Date**: 2026-08-16
**Surface**: Backend API
**Severity**: Security Enhancement

## Summary

Re-enabled Cloudflare Turnstile verification for login endpoint after fixing dependency injection issues.

## Background

Turnstile was temporarily disabled during debugging of 500 errors on login. The root causes have been fixed:
1. TurnstileService dependency injection conflict (removed duplicate singleton)
2. Credit balance endpoint type errors (fixed dataclass access)

## Changes

### Backend
- `platform_api/routers/auth.py` - Login endpoint:
  - Re-enabled `turnstile: TurnstileServiceDep` parameter
  - Re-enabled Turnstile token verification logic
  - Bot verification now active for both login and register

### Security

**Bot Protection Active:**
- Login requires valid Turnstile token from frontend
- Register requires valid Turnstile token from frontend
- Invalid tokens return 422 validation error
- Missing tokens are allowed (desktop app compatibility)

**Configuration:**
- Sandbox uses Turnstile site key: `0x4AAAAAAERrvCRyn8xcIet3`
- Secret key configured in `.deploy/secrets.sandbox.env`

## Testing

Manual test on sandbox:
1. Visit `https://music.sandbox.camxora.com/login`
2. Complete Turnstile challenge
3. Submit login credentials
4. Should succeed with valid token

Bot test:
1. Send login request without `cf_turnstile_response`
2. Should be allowed (for desktop app compatibility)
3. Send login with invalid token
4. Should fail with validation error

## Related

- Fixes Phase 1 Priority 1 task: Cloudflare Turnstile integration
- Part of comprehensive bot protection strategy
