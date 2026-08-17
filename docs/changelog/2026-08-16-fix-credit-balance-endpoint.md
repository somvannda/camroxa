# Fix Credit Balance Endpoint (500 Error)

**Date**: 2026-08-16
**Surface**: Backend API
**Severity**: Critical Bug Fix

## Problem

The `/api/v1/v2/credits/balance` endpoint was returning 500 errors for users without an active subscription.

**Root Cause**: 
- The endpoint was accessing `get_detailed_balance()` return value as a dictionary
- `get_detailed_balance()` actually returns a `DetailedBalance` dataclass (or `None`)
- For users without subscriptions, it returned `None`, causing `TypeError: 'NoneType' object is not subscriptable`

## Changes

### Backend
- `platform_api/routers/v2_credits.py` - `/balance` endpoint:
  - Added null check for users without subscriptions
  - Fixed dataclass property access (was treating it as dict)
  - Returns zero balance gracefully for non-subscribers

## Testing

Manual test:
1. Login to music web (user without subscription)
2. Check credit balance display
3. Should show 0 credits instead of error

## Related

- Follows up on login fix (Turnstile verification)
- Part of Phase 1 web music credit system
