# Add Comprehensive Logging for Debugging

**Date**: 2026-08-16
**Surface**: Backend API
**Severity**: Development/Debugging

## Summary

Added detailed logging to all critical authentication and credit endpoints to diagnose 500 errors.

## Changes

### Backend Logging Enhancements

**`platform_api/routers/auth.py` - Login endpoint:**
- Log every step of the login process
- Log Turnstile verification attempts and results
- Log authentication attempts and outcomes
- Catch and log all unexpected errors with full stack traces

**`platform_api/routers/v2_credits.py` - Credit balance endpoint:**
- Log user ID for each balance request
- Log database query results
- Log when users have no subscription
- Catch and log all errors with full details

**`platform_api/services/shared/turnstile_service.py` - Turnstile verification:**
- Log token verification requests
- Log Cloudflare API responses
- Log success/failure reasons
- Enhanced error logging with exception details

**`platform_api/services/v2/credit_service.py` - Credit service:**
- Log database queries and results
- Log balance calculations
- Catch and log database errors

## Log Locations

Logs will appear in:
- Sandbox: `journalctl -u camxora-api -f`
- Check with: `python scripts/deploy/check_api_errors.py`

## Expected Log Output

### Successful Login:
```
INFO: Login attempt: email=user@example.com, has_turnstile=True
INFO: Verifying Turnstile token...
INFO: Turnstile verification result: True
INFO: Checking account lockout status...
INFO: Authenticating user...
INFO: Authentication successful, resetting failure counter...
INFO: Setting auth cookies...
INFO: Login successful
```

### Failed Login:
```
INFO: Login attempt: email=user@example.com, has_turnstile=True
ERROR: Turnstile verification error: TypeError: ...
```

## Purpose

These logs will help identify:
1. Where exactly the 500 errors are occurring
2. What exceptions are being raised
3. Database query issues
4. Turnstile API communication problems
5. Dependency injection failures

## Next Steps

After deployment, monitor logs during login attempts to identify root cause of 500 errors.
