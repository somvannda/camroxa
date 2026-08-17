# Fix Turnstile Parameter Name Bug

**Date**: 2026-08-16
**Surface**: Backend API  
**Severity**: Critical Bug Fix

## Problem

Login and register endpoints were failing with 500 errors due to incorrect parameter name when calling Turnstile verification.

**Error**:
```
TypeError: TurnstileService.verify() got an unexpected keyword argument 'ip'
```

## Root Cause

The `TurnstileService.verify()` method signature uses `remote_ip` as the parameter name, but the login and register endpoints were calling it with `ip`.

**Method signature:**
```python
async def verify(self, token: str, remote_ip: Optional[str] = None) -> bool:
```

**Incorrect call:**
```python
await turnstile.verify(token, ip=client_ip)  # WRONG
```

## Fix

Updated both login and register endpoints to use the correct parameter name:
```python
await turnstile.verify(token, remote_ip=client_ip)  # CORRECT
```

### Files Changed
- `platform_api/routers/auth.py`:
  - Fixed login endpoint Turnstile call
  - Fixed register endpoint Turnstile call

## Testing

After deployment:
1. Visit `https://music.sandbox.camxora.com/login`
2. Complete Turnstile challenge
3. Submit login credentials
4. Should succeed without 500 error

## Impact

This fix resolves the 500 errors on login/register that have been blocking user access. Bot protection is now fully functional.

## Lessons Learned

- Comprehensive logging was essential for diagnosing this issue
- Parameter names must match exactly between function signatures and calls
- Always test the full flow after re-enabling features
