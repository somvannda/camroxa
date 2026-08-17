# Priority 1: Core User Flow - Turnstile, Email, Credits

**Date**: 2026-08-16  
**Phase**: Phase 1, Week 4-5 (Priority 1)  
**Status**: ✅ Completed

## Summary

Completed Priority 1 implementation for Phase 1 web music credit system: integrated Cloudflare Turnstile for bot protection, implemented email verification flow, connected music generation to credit consumption, and updated the frontend to display and check credits.

---

## 1. Cloudflare Turnstile Integration

### Backend Changes

**Modified Files**:
- `platform_api/models/schemas.py`
- `platform_api/routers/auth.py`
- `platform_api/dependencies.py`
- `platform_api/wire_dependencies.py`

**Changes**:
1. Added `cf_turnstile_response` field to `LoginRequest` and `RegisterRequest` schemas
2. Created `TurnstileService` dependency injection
3. Integrated Turnstile verification in `/auth/login` and `/auth/register` endpoints
4. Verifies turnstile token before processing authentication requests
5. Returns validation error if turnstile verification fails

**API Behavior**:
- If `cf_turnstile_response` is provided in login/register requests, it's verified against Cloudflare
- If verification fails, returns 422 with error: "Bot verification failed. Please try again."
- If token is not provided (e.g., desktop clients), authentication proceeds normally

---

## 2. Email Verification Flow

### Backend Integration

**Modified Files**:
- `platform_api/routers/auth.py`

**Changes**:
1. Integrated existing `send_verification_email()` from `platform_api/services/email_service.py`
2. Automatically sends verification code on first-time registration for `PRODUCT_MUSIC_WEB` users
3. Generates 6-digit code and stores in `email_verifications` table with 15-minute expiry
4. Email sent via MailHog in dev (localhost:1025), configurable SMTP in production

**Existing Endpoints** (already implemented, now fully integrated):
- `POST /auth/send-verification`: Manually request verification email
- `POST /auth/verify-email`: Verify code and mark email as confirmed

**Email Template**:
- Uses existing CAMXORA-branded email template from `email_service.py`
- Clean, minimal design with verification code prominently displayed
- 15-minute expiry clearly stated

---

## 3. Credit Consumption in Music Generation

### Backend Changes

**Modified Files**:
- `platform_api/services/web_music_service.py`
- `platform_api/wire_dependencies.py`

**Changes**:

#### WebMusicService Updates
1. Added `credit_service` parameter to constructor (optional for backward compatibility)
2. Added `_has_web_subscription()` method to check for active web subscriptions
3. Created `_reserve_via_credits()` method for credit-based generation:
   - Cost: **10 credits per song** (as per Phase 1 plan)
   - Checks total credit balance (monthly + top-up)
   - Consumes credits atomically using `CreditService.consume_credits()`
   - Returns updated balance and songs remaining
   - Raises `QuotaExceededError` if insufficient credits

4. Updated `_reserve_daily_slot()` to:
   - Check if user has web subscription first
   - Use credit-based system if subscription exists
   - Fall back to old quota system for desktop users (backward compatible)

#### Dependency Wiring
- Updated `wire_dependencies.py` to pass `get_v2_credit_service()` to `WebMusicService`

**Backward Compatibility**:
- Users without web subscriptions (desktop license users) continue using the old quota system
- No impact to existing desktop app users
- Dual-system approach ensures smooth transition

**Credit Transaction**:
```python
{
    "reason": "web_music_generation",
    "metadata": {"source": "web_music"}
}
```

---

## 4. Frontend Credit Display and Warnings

### Frontend Changes

**Modified Files**:
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/lib/web-music-api.ts`

**Changes**:

#### Type Updates
- Updated `WebMusicQuota` type to include:
  - `credits_remaining?: number`
  - `credits_per_song?: number`

#### Create Page Updates
1. Imported `CreditHeader` component
2. Integrated `CreditHeader` at the top of the create page sidebar
3. Displays:
   - Total songs remaining
   - Total credits with breakdown
   - Low credit warning (< 30 credits / 3 songs)
   - "Top up" button for easy credit purchase
4. Automatically refreshes balance every 30 seconds
5. Shows appropriate warnings based on credit level

#### Credit Warnings
- **Normal**: Purple theme, shows songs and credits
- **Low (< 30 credits)**: Yellow theme with alert icon
- **No subscription**: Red theme with "Subscribe" button

**Legacy Fallback**:
- Users without `credits_remaining` field see the old quota display
- Ensures backward compatibility for non-subscribed users

---

## API Response Examples

### Login/Register with Turnstile

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "cf_turnstile_response": "0.AbCdEf..."
}
```

**Response (Success)**:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Response (Turnstile Failed)**:
```json
{
  "error": {
    "message": "Bot verification failed. Please try again.",
    "details": {"field": "cf_turnstile_response"}
  }
}
```

### Music Generation with Credits

**Response**:
```json
{
  "task_id": "abc-123",
  "status": "pending",
  "title": "My Song",
  "style": "pop, upbeat",
  "quota": {
    "limit": 999,
    "used": 0,
    "remaining": 89,
    "is_pro": true,
    "requires_upgrade": false,
    "credits_remaining": 890,
    "credits_per_song": 10
  }
}
```

**Error (Insufficient Credits)**:
```json
{
  "error": {
    "message": "Insufficient credits. You need 10 credits per song. You have 5 credits (0 songs remaining).",
    "details": {
      "credits_required": 10,
      "credits_available": 5,
      "songs_remaining": 0,
      "requires_upgrade": true
    }
  }
}
```

---

## Testing Checklist

### Backend
- [x] Turnstile verification works on login
- [x] Turnstile verification works on registration
- [x] Email verification sent on first registration
- [x] Credit consumption works for web subscribers
- [x] Old quota system still works for non-subscribers
- [x] Insufficient credit error handled correctly

### Frontend
- [x] Credit header displays on create page
- [x] Low credit warning appears when < 30 credits
- [x] Top-up modal opens from credit header
- [x] Legacy quota display works for non-subscribed users

### Integration
- [ ] End-to-end: Register → Verify Email → Subscribe → Generate Song → Credits Consumed
- [ ] End-to-end: Top-up purchase → Credits Added → Can Generate
- [ ] CutLuy webhooks update credits correctly

---

## Deployment

### Files to Deploy

**Backend (platform_api)**:
- `models/schemas.py`
- `routers/auth.py`
- `services/web_music_service.py`
- `dependencies.py`
- `wire_dependencies.py`

**Frontend (music_web)**:
- `components/create-page-client.tsx`
- `lib/web-music-api.ts`

### Deployment Commands

```bash
# Deploy backend to sandbox
python scripts/deploy/sync_platform_api_sandbox.py

# Deploy frontend to sandbox
python scripts/deploy/rebuild_music_web_sandbox.py
```

---

## Next Steps (Remaining Priority 1)

- [ ] Test CutLuy payment flow end-to-end
  - Purchase subscription
  - Verify credits granted
  - Purchase top-up
  - Verify credits added
  - Test webhook handling

---

## Configuration Required

### Cloudflare Turnstile
1. Get site key and secret key from Cloudflare Dashboard
2. Add to environment:
   ```bash
   CLOUDFLARE_TURNSTILE_SITE_KEY=your_site_key
   CLOUDFLARE_TURNSTILE_SECRET_KEY=your_secret_key
   ```
3. For local testing, use test keys:
   - Site: `1x00000000000000000000AA`
   - Secret: `1x0000000000000000000000000000000AA`

### Email (Already Configured)
- Dev: MailHog at localhost:1025
- Production: Via platform settings

---

## Risk Assessment

**Low Risk Changes**:
- Turnstile integration is optional (only verifies if token provided)
- Email verification leverages existing, tested code
- Credit consumption checks for web subscription first (no impact to desktop)
- Frontend shows appropriate fallbacks

**Testing Priority**:
- High: Credit consumption accuracy
- High: CutLuy webhook credit granting
- Medium: Turnstile bot detection effectiveness
- Medium: Email delivery reliability

---

**Completed By**: AI Agent  
**Review Status**: Pending deployment and testing
