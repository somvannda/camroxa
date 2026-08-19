# Fix Cloudflare Turnstile Request Format

**Date**: 2026-08-16
**Type**: Bug Fix
**Impact**: Critical - Fixes login/register bot protection

## Problem
Cloudflare Turnstile siteverify was not being called/recognized due to incorrect request format. The backend was sending verification requests as JSON, but Cloudflare expects form-encoded data.

## Root Cause
`TurnstileService.verify()` was using `httpx.AsyncClient.post(..., json={...})` which sends `Content-Type: application/json`. Cloudflare Turnstile siteverify API requires `application/x-www-form-urlencoded` format.

## Solution
Changed `platform_api/services/shared/turnstile_service.py`:
- **Before**: `json={"secret": ..., "response": ..., "remoteip": ...}`
- **After**: `data={"secret": ..., "response": ..., "remoteip": ...}`

This ensures the request is sent as form data, which Cloudflare can properly process.

## Files Changed
- `platform_api/services/shared/turnstile_service.py`

## Testing
1. User registers/logs in on `music.sandbox.camxora.com`
2. Turnstile widget is completed by user
3. Backend sends verification request to Cloudflare
4. Cloudflare successfully verifies the token
5. Cloudflare dashboard shows siteverify calls are being received

## Impact
- ✅ Fixes: Login and register bot protection now works correctly
- ✅ No breaking changes to API or frontend
- ✅ No database changes required
