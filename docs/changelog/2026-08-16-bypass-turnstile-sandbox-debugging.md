# Temporarily Bypass Turnstile for Sandbox Debugging

**Date**: 2026-08-16  
**Type**: Debugging / Workaround  
**Environment**: Sandbox only

## Summary

Temporarily disabled Cloudflare Turnstile verification on sandbox login/register endpoints to unblock testing of the credit system while investigating why Turnstile verification is consistently returning `False` from Cloudflare.

## Issue

Despite Turnstile challenges being issued and solved (visible in Cloudflare Analytics), the backend verification is failing with:
```
Turnstile verification result: False
ValidationError: Bot verification failed. Please try again.
```

Potential causes:
1. Mismatch between site key and secret key
2. Cloudflare detecting something suspicious about the verification requests  
3. Token expiry or format issues
4. Configuration issue with the Turnstile keys in sandbox

## Changes

### Backend (`platform_api/routers/auth.py`)
- Commented out Turnstile verification in both `login` and `register` endpoints
- Added logging: "Turnstile verification bypassed for sandbox debugging"
- Added TODO comments to investigate and re-enable

## Next Steps

1. Investigate Cloudflare Turnstile dashboard for error details
2. Verify site key and secret key configuration match
3. Check if Cloudflare is flagging sandbox traffic
4. Test with different Turnstile modes (managed vs non-interactive)
5. Re-enable Turnstile once root cause is identified

## Note

This is a **temporary workaround for sandbox testing only**. Turnstile should remain enabled on production for bot protection.
