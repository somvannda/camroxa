# Add Enhanced Turnstile Debug Logging

**Date**: 2026-08-16
**Type**: Debug Enhancement
**Impact**: Debugging - Additional logging for Turnstile verification

## Purpose
Add detailed debug logging to diagnose why Turnstile verification is consistently returning False without any logs from the TurnstileService itself.

## Changes
Added debug logging in `platform_api/routers/auth.py` login endpoint to log:
- Turnstile token (first 20 chars)
- Client IP address
- Turnstile verification result type and value

## Files Changed
- `platform_api/routers/auth.py`

## Next Steps
After deployment, these logs will help identify:
1. Whether the Turnstile token is being passed correctly
2. Whether the client IP is correct
3. The exact return type and value from TurnstileService.verify()
