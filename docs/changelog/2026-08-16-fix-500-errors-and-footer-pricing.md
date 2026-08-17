# Fix 500 Errors and Footer Pricing Link

**Date**: 2026-08-16  
**Type**: Bug Fix  
**Severity**: Critical (prevented login and plan viewing)

## Problems

1. **500 errors on login endpoint** (`/api/v1/auth/login`)
2. **500 errors on subscription plans endpoint** (`/api/v1/v2/subscriptions/plans`)
3. **React hydration error #418** (caused by backend failures)
4. **Footer pricing link** pointed to external website instead of modal

## Root Cause

The `TurnstileService` in `platform_api/services/shared/turnstile_service.py` had a broken singleton getter function that was calling the constructor without the required `settings` parameter:

```python
# BROKEN CODE (removed):
def get_turnstile_service() -> TurnstileService:
    global _turnstile_service
    if _turnstile_service is None:
        _turnstile_service = TurnstileService()  # ❌ Missing settings parameter!
    return _turnstile_service
```

This caused a `TypeError` whenever the auth or subscription endpoints tried to initialize the service, resulting in 500 errors.

## Solution

### Backend Fix

Removed the broken singleton getter from `turnstile_service.py`. The correct dependency injection is already implemented in `platform_api/dependencies.py`:

```python
# CORRECT CODE (in dependencies.py):
def get_turnstile_service():
    from platform_api.services.shared.turnstile_service import TurnstileService
    return TurnstileService(get_settings())  # ✅ Passes settings correctly
```

**File changed**: `platform_api/services/shared/turnstile_service.py`
- Removed lines 122-135 (broken singleton code)

### Frontend Fix

Updated `SiteFooter` component to open the pricing modal instead of linking to external website:

**Changes**:
- Made `SiteFooter` a client component (`'use client'`)
- Added `PricingModal` state management
- Changed pricing link from `<a href={website}/pricing>` to button with `onClick` handler
- Updated `FooterColumn` to support `onClick` handlers
- Added `PricingModal` rendering

**File changed**: `music_web/src/components/site-footer.tsx`

## Impact

### Before
- ❌ Login failed with 500 error
- ❌ Pricing plans failed to load with 500 error
- ❌ React hydration errors
- ❌ Footer pricing link went to external website

### After
- ✅ Login works correctly
- ✅ Pricing plans load successfully
- ✅ No more hydration errors
- ✅ Footer pricing link opens modal with database-driven plans

## Testing

- ✅ Backend deployed to sandbox
- ✅ Frontend deployed to sandbox
- ✅ Login endpoint returns 200
- ✅ Plans endpoint returns 200
- ✅ Footer pricing button opens modal

## Technical Notes

The issue occurred because we had two conflicting `get_turnstile_service()` functions:
1. In `turnstile_service.py` - broken singleton (now removed)
2. In `dependencies.py` - correct implementation (kept)

The FastAPI dependency injection system uses the one from `dependencies.py` via `wire_dependencies.py`, but the broken one in the service file was interfering during module imports.
