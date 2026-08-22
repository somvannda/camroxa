# Camxora Credits-Only Plan Unification — Test Matrix

**Status:** Draft  
**Date:** 2026-08-22  
**Scope:** Complete test plan for credits-only v3 plan unification across all surfaces

---

## How to Run Each Surface

### Platform API (Backend)

**Local:**
```bash
cd /workspace
export PLATFORM_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/platform_db
export PLATFORM_REDIS_URL=redis://localhost:6379/0
export PLATFORM_JWT_SECRET=your-secret-here
uvicorn platform_api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Sandbox API:** `https://api-sandbox.camxora.com` (requires VPN or sandbox SSH)

**Tests:**
```bash
cd /workspace
pytest platform_api/tests/test_channel_setup_credits.py -v
pytest platform_api/tests/ -k credits -v
```

**Smoke test:**
```bash
curl -X GET http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234"}'
```

---

### Admin Portal

**Local:**
```bash
cd /workspace/admin_portal
npm install
npm run dev
# Opens at http://localhost:5173
```

**Sandbox:** `https://admin-sandbox.camxora.com` (requires auth)

**Login:** Admin credentials from sandbox `.env`

---

### Music Web

**Local:**
```bash
cd /workspace/music_web
npm install
npm run dev
# Opens at http://localhost:3003
```

**Sandbox:** `https://music-sandbox.camxora.com`

**Test Account:** Create via `/signup` or use existing sandbox user

---

### Website (Marketing)

**Local:**
```bash
cd /workspace/website
npm install
npm run dev
# Opens at http://localhost:3000
```

**Sandbox:** `https://sandbox.camxora.com` (if deployed)

**Production:** `https://camxora.com` (READ-ONLY for test verification)

---

### User Portal

**Local:**
```bash
cd /workspace/user_portal
npm install
npm run dev
# Opens at http://localhost:3000 (default Next.js port)
```

**Sandbox:** TBD (check deployment docs)

---

### Desktop App (Electron/Python)

The desktop app mentioned as `D:\Development\Projects\Electron\MusicGenerator-credits-only-api-v3` appears to be a different local path. For the workspace version:

**Electron Desktop (camxora):**
```bash
cd /workspace/camxora
npm install
npm run dev
# Electron window opens
```

**Python Desktop (camxora_python) - if standalone:**
```bash
cd /workspace/camxora_python
pip install -e .
python main.py
```

**Note:** Desktop app connects to `localhost:8000` API by default. Check `.env` files for API endpoint configuration.

---

## Product Lock Requirements

These are the **immutable product rules** all tests must validate against:

1. **Billing = Credits**: Plans define cash price + monthly credit grant + per-operation credit costs + is_active/is_public flags
2. **Public Cards (3 tiers):**
   - Starter: $10/mo → 1,000 credits/mo
   - Creator: $30/mo → 3,500 credits/mo
   - Studio: $60/mo → 8,000 credits/mo
   - Dual-channel feature is a bullet point (not a separate SKU)
   - Song generation hint: `floor(monthly_credits / 10)` (never x2 for dual-channel)
3. **Hidden $79 Desktop Monthly:**
   - Stays same `plan_id`, `is_active=true`, `is_public=false`
   - MUST NOT appear on website/portal/music_web pricing pages
4. **Free Plan:**
   - $0 plan row with `daily_credits` field (e.g., 50 credits/day)
   - NOT a separate system setting or charge flag
5. **Profiles ≠ Plans:**
   - $5/$10 dual-profile addon packs **do not multiply credits**
   - Profile packs only add channel slots
6. **Conversion (One-Time):**
   - Leftover song packages × 10 = credits minted once
   - Expired licenses mint 0
   - Lifetime licenses skip conversion
   - Draft/image/video packages do NOT mint credits
7. **Charge Flag:**
   - `credits_only_v3_charge` system setting can be flipped ON for sandbox tests
   - Production flip is **out of scope** for this test plan
8. **Two Ledgers Still Exist:**
   - Web: integer credits (music_web, user_portal)
   - Desktop: micro-unit credits (camxora app)
   - One charge model, but not yet one unified wallet

---

## Test Cases

### Category A: Public Plan Visibility & Filtering

#### TC-A01: Public plans list (v1 desktop API)

- **Surface:** `platform_api` (`GET /api/v1/plans`)
- **Preconditions:**
  - Database has 3 public plans (Starter/Creator/Studio): `is_active=true`, `is_public=true`
  - Database has $79 Monthly plan: `is_active=true`, `is_public=false`
  - `credits_only_v3_charge` flag is OFF
- **Steps:**
  1. Start platform_api locally (`uvicorn platform_api.main:app ...`)
  2. Authenticate as admin user
  3. `curl -X GET http://localhost:8000/api/v1/plans -H "Authorization: Bearer <admin_token>"`
- **Expected:**
  - Response includes 3 public plans (Starter/Creator/Studio)
  - $79 plan is **excluded** (not in response)
  - Each plan has `is_public=true`, `is_active=true`
- **Failure Meaning:** v1 API still leaking hidden plans; product lock violated

---

#### TC-A02: Public plans list (v3 credits-only API)

- **Surface:** `platform_api` (hypothetical `GET /api/v3/plans`)
- **Preconditions:**
  - Same as TC-A01
  - `credits_only_v3_charge` flag is ON
- **Steps:**
  1. Start platform_api locally
  2. `curl -X GET http://localhost:8000/api/v3/plans`
- **Expected:**
  - Response includes only plans where `is_active=true AND is_public=true`
  - $79 plan **excluded**
  - Each plan shows `monthly_credits` field
- **Failure Meaning:** v3 API public filter broken

---

#### TC-A03: Hidden $79 plan leak on website pricing page

- **Surface:** `website` (`/pricing`)
- **Preconditions:**
  - Website deployed to sandbox or running locally
  - Database has $79 plan with `is_public=false`
- **Steps:**
  1. Open `http://localhost:3000/pricing` (or sandbox URL)
  2. Inspect pricing cards
- **Expected:**
  - Exactly 3 pricing tiers shown: Starter ($10), Creator ($30), Studio ($60)
  - No $79 card visible
  - No mention of "Desktop Monthly" legacy plan
- **Failure Meaning:** Frontend not filtering `is_public=false` plans; product leak risk

---

#### TC-A04: Hidden $79 plan leak on music_web pricing

- **Surface:** `music_web` (`/pricing` or pricing modal)
- **Preconditions:**
  - music_web running locally (`npm run dev` in `/workspace/music_web`)
  - API returns plans including hidden $79
- **Steps:**
  1. Open `http://localhost:3003/pricing`
  2. Click "Upgrade" or "Pricing" button
- **Expected:**
  - Pricing modal shows only 3 public plans
  - $79 plan **not shown**
- **Failure Meaning:** music_web not filtering hidden plans

---

#### TC-A05: Hidden $79 plan leak on user_portal onboarding

- **Surface:** `user_portal` (onboarding flow)
- **Preconditions:**
  - New user registration flow
  - user_portal running locally
- **Steps:**
  1. Register new user at `http://localhost:3000/signup`
  2. Complete onboarding wizard
  3. Reach plan selection screen
- **Expected:**
  - Only 3 public plans shown
  - $79 legacy plan hidden
- **Failure Meaning:** Onboarding leaking legacy plans to new users

---

### Category B: Admin Portal Plan Management

#### TC-B01: Admin plan catalog shows all plans (not quota editor)

- **Surface:** `admin_portal` (`/plans`)
- **Preconditions:**
  - Admin logged in
  - Database has public + hidden plans
- **Steps:**
  1. Open `http://localhost:5173/plans`
  2. View plan list
- **Expected:**
  - All plans visible (both `is_public=true` and `is_public=false`)
  - Each plan row shows `is_public` flag
  - Plan editor available (not old quota top-up UI)
  - Can edit `monthly_credits`, `is_active`, `is_public` fields
- **Failure Meaning:** Admin cannot manage hidden plans; wrong UI loaded

---

#### TC-B02: Admin plan catalog filter by plan_type

- **Surface:** `admin_portal` (`/plans`)
- **Preconditions:**
  - Database has both `desktop_pro` and `web_music` plans
- **Steps:**
  1. Open `/plans`
  2. Filter by `plan_type=desktop_pro`
  3. Filter by `plan_type=web_music`
- **Expected:**
  - Filters work correctly
  - Desktop plans and web music plans are separate sections
- **Failure Meaning:** Admin UI not supporting plan_type segmentation

---

#### TC-B03: Admin user detail shows wallet balance (not quota top-up button)

- **Surface:** `admin_portal` (`/users/{id}`)
- **Preconditions:**
  - Admin logged in
  - User has credit wallet with balance
- **Steps:**
  1. Open `/users/{user_id}`
  2. View credit section
- **Expected:**
  - Credit wallet balance displayed
  - Grant/deduct credits buttons available
  - NO "quota top-up" button (old system)
- **Failure Meaning:** Admin UI showing legacy quota system instead of credits

---

#### TC-B04: Admin usage/finance/user-spent reports show credits

- **Surface:** `admin_portal` (`/stats`, `/finance`, `/users/{id}/usage`)
- **Preconditions:**
  - User has consumed credits for generation
- **Steps:**
  1. Navigate to usage stats page
  2. View user spend report
  3. Check finance dashboard
- **Expected:**
  - All reports use "credits" terminology
  - No references to "quota" or "song packages"
- **Failure Meaning:** Admin reports not migrated to credits language

---

### Category C: Credits-Only V3 API Endpoints

#### TC-C01: Quote generation cost (v3 API)

- **Surface:** `platform_api` (`POST /api/v3/generation/quote`)
- **Preconditions:**
  - User authenticated
  - `credits_only_v3_charge` flag ON
- **Steps:**
  1. `curl -X POST http://localhost:8000/api/v3/generation/quote -H "Authorization: Bearer <token>" -d '{"operation":"song","count":1}'`
- **Expected:**
  - Response: `{"credits_required": 10, "balance": <user_balance>}`
- **Failure Meaning:** Quote endpoint not implemented or wrong credit amount

---

#### TC-C02: Charge 10 credits for song generation (flag ON)

- **Surface:** `platform_api` (`POST /api/v3/generation/song`)
- **Preconditions:**
  - User wallet has 50 credits
  - `credits_only_v3_charge` flag ON
- **Steps:**
  1. Generate 1 song via API
  2. Check wallet balance after completion
- **Expected:**
  - Balance reduced by 10 credits (50 → 40)
  - Transaction log shows "song_generation" debit
- **Failure Meaning:** v3 charge logic not working

---

#### TC-C03: Charge produces 2 versions after flag ON

- **Surface:** `platform_api` (`POST /api/v3/generation/song`)
- **Preconditions:**
  - User wallet has 50 credits
  - `credits_only_v3_charge` flag ON
  - Suno configured for 2 versions per song
- **Steps:**
  1. Generate 1 song
  2. Wait for Suno callback
  3. Check generated artifacts
- **Expected:**
  - 2 song versions created (as configured in Suno)
  - Only 10 credits charged (not 20)
  - Per-version credit cost is `10 / 2 = 5` effective cost per version
- **Failure Meaning:** Charging per version instead of per generation request

---

#### TC-C04: 402 Insufficient Credits when wallet 0 and no grant

- **Surface:** `platform_api` (`POST /api/v3/generation/song`)
- **Preconditions:**
  - User wallet balance = 0
  - User has no active plan (no monthly grant)
  - `credits_only_v3_charge` flag ON
- **Steps:**
  1. Attempt to generate 1 song
- **Expected:**
  - HTTP 402 Payment Required
  - Error message: "Insufficient credits"
  - No charge to external APIs (Suno not called)
- **Failure Meaning:** Charge gate not enforced; free API abuse possible

---

#### TC-C05: Refund on generation failure

- **Surface:** `platform_api` (generation service)
- **Preconditions:**
  - User wallet has 50 credits
  - `credits_only_v3_charge` flag ON
  - Suno API mock returns 500 error
- **Steps:**
  1. Generate 1 song
  2. Suno API fails
- **Expected:**
  - Wallet balance refunded (50 → 40 → 50)
  - Transaction log shows debit + credit (refund)
  - User notified of failure
- **Failure Meaning:** Refund logic not implemented; user loses credits on failure

---

#### TC-C06: Credits-only wallet operations

- **Surface:** `platform_api` (`GET /api/v3/credits/wallet`)
- **Preconditions:**
  - User authenticated
  - `credits_only_v3_charge` flag ON
- **Steps:**
  1. `curl -X GET http://localhost:8000/api/v3/credits/wallet -H "Authorization: Bearer <token>"`
- **Expected:**
  - Response: `{"balance": <int>, "monthly_grant": <int>, "daily_grant": <int>, "next_reset": "<ISO8601>"}`
- **Failure Meaning:** Wallet API not implemented

---

### Category D: Free Plan Daily Grant

#### TC-D01: Free plan daily grant from Free plan row

- **Surface:** `platform_api` (credit grant service)
- **Preconditions:**
  - Database has Free plan: `price_cents=0`, `monthly_credits=0`, `daily_credits=50`
  - User assigned Free plan
  - `credits_only_v3_charge` flag ON
- **Steps:**
  1. User logs in at start of day
  2. Check wallet balance
  3. Wait 24 hours (or mock system time)
  4. Check wallet balance again
- **Expected:**
  - First check: `balance = 50` (daily grant applied)
  - After 24h: `balance = 50` (if unused) or `balance = previous + 50` (if partially used)
  - Daily grant does NOT stack beyond cap (if configured)
- **Failure Meaning:** Daily grant not implemented or using legacy system setting

---

#### TC-D02: Free plan row exists with daily_credits field

- **Surface:** `platform_api` (database query)
- **Preconditions:**
  - Database migration applied
- **Steps:**
  1. `psql -c "SELECT id, name, price_cents, daily_credits FROM plans WHERE price_cents = 0;"`
- **Expected:**
  - At least one row returned
  - `price_cents = 0`, `daily_credits > 0` (e.g., 50)
- **Failure Meaning:** Free plan not created as plan row; legacy system still in use

---

### Category E: Monthly/Period Grant on Unexpired License

#### TC-E01: Monthly grant applied on subscription start

- **Surface:** `platform_api` (subscription service)
- **Preconditions:**
  - User purchases Starter plan ($10/mo, 1000 credits)
  - Subscription status = active
  - License not expired
- **Steps:**
  1. Complete checkout
  2. Check wallet balance immediately
- **Expected:**
  - Wallet balance shows `monthly_grant: 1000`
  - Credits available for use
- **Failure Meaning:** Grant not applied on subscription activation

---

#### TC-E02: Monthly grant NOT applied on expired license

- **Surface:** `platform_api` (license check)
- **Preconditions:**
  - User had Starter plan
  - License expired 1 day ago
  - Wallet had 100 credits remaining from previous period
- **Steps:**
  1. User logs in
  2. Check wallet balance
- **Expected:**
  - No new monthly grant applied
  - Wallet shows only leftover 100 credits (or 0 if monthly credits don't roll over)
- **Failure Meaning:** Grant applied to expired license; revenue leakage

---

#### TC-E03: Monthly grant reset on billing cycle

- **Surface:** `platform_api` (subscription renewal)
- **Preconditions:**
  - User has Starter plan ($10/mo, 1000 credits)
  - User consumed 300 credits in previous month
  - Billing cycle renews
- **Steps:**
  1. Wait for billing renewal (or mock system time)
  2. Check wallet after renewal
- **Expected:**
  - Monthly grant reset to 1000 credits
  - Previous 700 unused credits either:
    - Forfeited (if no rollover policy), OR
    - Rolled over (if rollover enabled - check product rules)
- **Failure Meaning:** Grant reset logic broken

---

### Category F: Conversion (One-Time) Logic

#### TC-F01: Conversion dry-run (preview mode)

- **Surface:** `platform_api` (`POST /api/v1/admin/conversion/dry-run`)
- **Preconditions:**
  - Admin authenticated
  - User has legacy data: 50 song packages remaining, no Lifetime license
- **Steps:**
  1. `curl -X POST http://localhost:8000/api/v1/admin/conversion/dry-run -d '{"user_id":"<uuid>"}'`
- **Expected:**
  - Response: `{"credits_to_mint": 500, "reason": "50 song packages × 10"}`
  - No database changes
- **Failure Meaning:** Dry-run modifying database; unsafe to test

---

#### TC-F02: Conversion apply confirm gate

- **Surface:** `platform_api` (`POST /api/v1/admin/conversion/apply`)
- **Preconditions:**
  - Dry-run completed successfully
  - Admin confirms conversion
- **Steps:**
  1. `curl -X POST http://localhost:8000/api/v1/admin/conversion/apply -d '{"user_id":"<uuid>","confirmed":true}'`
  2. Check wallet balance
- **Expected:**
  - Wallet balance increased by 500 credits
  - Conversion marked as completed (cannot run twice)
- **Failure Meaning:** Conversion not gated by confirmation; risk of accidental double-mint

---

#### TC-F03: Leftover song packages × 10 = credits

- **Surface:** `platform_api` (conversion service)
- **Preconditions:**
  - User has 73 song packages remaining (legacy quota system)
- **Steps:**
  1. Run conversion for user
- **Expected:**
  - Credits minted: `73 × 10 = 730`
- **Failure Meaning:** Conversion math wrong

---

#### TC-F04: Expired license mints 0 credits

- **Surface:** `platform_api` (conversion service)
- **Preconditions:**
  - User had legacy license expired 30 days ago
  - Had 50 song packages at expiry
- **Steps:**
  1. Run conversion for user
- **Expected:**
  - Credits minted: 0
  - Reason: "License expired; no conversion"
- **Failure Meaning:** Converting expired licenses; revenue loss

---

#### TC-F05: Lifetime license skips conversion

- **Surface:** `platform_api` (conversion service)
- **Preconditions:**
  - User has Lifetime license
  - Had 100 song packages (shouldn't exist for Lifetime, but edge case)
- **Steps:**
  1. Run conversion for user
- **Expected:**
  - Credits minted: 0
  - Reason: "Lifetime license skipped"
  - Lifetime users remain on legacy quota system (or have separate rule)
- **Failure Meaning:** Converting Lifetime users incorrectly

---

#### TC-F06: Draft/image/video packages do NOT mint credits

- **Surface:** `platform_api` (conversion service)
- **Preconditions:**
  - User has:
    - 50 song packages
    - 100 draft packages
    - 20 image packages
    - 10 video packages
- **Steps:**
  1. Run conversion for user
- **Expected:**
  - Credits minted: `50 × 10 = 500` (song only)
  - Draft/image/video packages ignored
- **Failure Meaning:** Over-minting credits from non-song packages

---

### Category G: Desktop App (Electron/Python)

#### TC-G01: Desktop shows one credits number (not separate quota)

- **Surface:** `camxora` (desktop app UI)
- **Preconditions:**
  - Desktop app running locally (`npm run dev` in `/workspace/camxora`)
  - User logged in with Starter plan (1000 credits)
- **Steps:**
  1. Open desktop app
  2. Navigate to main generation screen
- **Expected:**
  - Single credits display: "1000 credits available"
  - No separate "song quota" or "draft quota" displays
- **Failure Meaning:** Desktop still using legacy quota UI

---

#### TC-G02: Desktop Generate button copy mentions credits

- **Surface:** `camxora` (desktop app)
- **Preconditions:**
  - Desktop app running
  - User has 100 credits
- **Steps:**
  1. Click "Generate Song" button (or equivalent)
- **Expected:**
  - Button shows "Generate (10 credits)" or similar
  - Tooltip: "This will cost 10 credits"
- **Failure Meaning:** Desktop UI not updated to credits terminology

---

#### TC-G03: Desktop does NOT show "Plan quota"

- **Surface:** `camxora` (desktop app)
- **Preconditions:**
  - Desktop app running
  - User has active plan
- **Steps:**
  1. Open settings or account screen
- **Expected:**
  - No "Plan quota: 300 songs/month" display
  - Only "Credits: 1000" or similar
- **Failure Meaning:** Legacy quota system still visible in desktop

---

#### TC-G04: Desktop connects to API v3 endpoints

- **Surface:** `camxora` (desktop app network)
- **Preconditions:**
  - Desktop app running
  - API v3 endpoints deployed
  - Network inspector open
- **Steps:**
  1. Perform any generation action
  2. Monitor network requests
- **Expected:**
  - Requests go to `/api/v3/...` endpoints
  - No requests to legacy `/api/v1/credits/...` (if deprecated)
- **Failure Meaning:** Desktop not migrated to v3 API

---

### Category H: Dual-Channel Profile Packs

#### TC-H01: $5 dual-profile pack does not add credits

- **Surface:** `platform_api` (`POST /api/v1/profiles/purchase-addon`)
- **Preconditions:**
  - User has Starter plan (1000 credits)
  - User has 1 channel profile
  - User wallet: 1000 credits
- **Steps:**
  1. Purchase $5 dual-profile pack
  2. Check wallet balance
  3. Check profile slot count
- **Expected:**
  - Wallet balance: still 1000 credits (unchanged)
  - Profile slots: increased from 1 to 3 (or +2 slots)
  - Payment processed for $5
- **Failure Meaning:** Profile pack incorrectly adding credits; product logic broken

---

#### TC-H02: $10 dual-profile pack does not add credits

- **Surface:** `platform_api` (`POST /api/v1/profiles/purchase-addon`)
- **Preconditions:**
  - User has Creator plan (3500 credits)
  - User wallet: 3500 credits
- **Steps:**
  1. Purchase $10 dual-profile pack
  2. Check wallet balance
- **Expected:**
  - Wallet balance: still 3500 credits (unchanged)
  - Profile slots increased
- **Failure Meaning:** Profile pack adding credits; product confusion

---

#### TC-H03: Song generation hint = floor(monthly_credits / 10)

- **Surface:** `platform_api` or frontend (pricing display)
- **Preconditions:**
  - Starter plan: 1000 credits/mo
  - Creator plan: 3500 credits/mo
  - Studio plan: 8000 credits/mo
- **Steps:**
  1. Query plan details or view pricing page
- **Expected:**
  - Starter: hint shows "~100 songs/mo" (`floor(1000/10)`)
  - Creator: hint shows "~350 songs/mo" (`floor(3500/10)`)
  - Studio: hint shows "~800 songs/mo" (`floor(8000/10)`)
  - NO "x2 for dual-channel" multiplier shown
- **Failure Meaning:** Song hint calculation wrong or showing dual-channel multiplier

---

### Category I: Hidden $79 Desktop Monthly Plan Renewal

#### TC-I01: Hidden $79 plan renew grants 3000 credits (not 1000)

- **Surface:** `platform_api` (subscription renewal)
- **Preconditions:**
  - User subscribed to hidden $79 Desktop Monthly plan
  - Plan row: `price_cents=7900`, `monthly_credits=3000`, `is_active=true`, `is_public=false`
  - Renewal date reached
- **Steps:**
  1. Trigger renewal (or wait for billing cycle)
  2. Check wallet balance after renewal
- **Expected:**
  - Monthly grant: 3000 credits (not 1000 like Starter)
  - $79 charged
  - Plan remains hidden (`is_public=false`)
- **Failure Meaning:** Hidden plan grant amount wrong; existing users under-credited

---

#### TC-I02: Hidden $79 plan does NOT appear in user_portal pricing

- **Surface:** `user_portal` (plan upgrade flow)
- **Preconditions:**
  - User logged in to user_portal
  - User on Free plan
  - Clicks "Upgrade"
- **Steps:**
  1. Navigate to upgrade/pricing page
- **Expected:**
  - Only 3 public plans shown (Starter/Creator/Studio)
  - $79 hidden plan NOT shown
- **Failure Meaning:** Hidden plan leaking to upgrade flow

---

### Category J: Website Pricing Page

#### TC-J01: Website pricing shows 3 cards only

- **Surface:** `website` (`/pricing`)
- **Preconditions:**
  - Website running locally or on sandbox
- **Steps:**
  1. Open `http://localhost:3000/pricing`
- **Expected:**
  - Exactly 3 pricing cards: Starter, Creator, Studio
  - Dual-channel feature listed as bullet point on each card (not separate SKU)
  - "~100 songs", "~350 songs", "~800 songs" hints shown (no x2 for dual-channel)
- **Failure Meaning:** Website not filtering plans correctly

---

#### TC-J02: Website pricing dual-channel is a bullet

- **Surface:** `website` (`/pricing`)
- **Preconditions:**
  - Pricing page loaded
- **Steps:**
  1. Read feature bullets for each plan card
- **Expected:**
  - Bullet: "✓ Dual-channel music generation" (or similar)
  - NOT a separate card or addon SKU
- **Failure Meaning:** Product positioning incorrect

---

### Category K: Music Web Pricing & Lyrics Cost

#### TC-K01: Music web pricing modal shows 3 plans

- **Surface:** `music_web` (pricing modal)
- **Preconditions:**
  - music_web running locally
  - User not subscribed
- **Steps:**
  1. Open `http://localhost:3003`
  2. Click "Get Started" or "Pricing"
- **Expected:**
  - Modal shows 3 plans: Starter, Creator, Studio
  - $79 hidden plan NOT shown
- **Failure Meaning:** music_web leaking hidden plans

---

#### TC-K02: Music web lyrics cost deducted from lyric amount

- **Surface:** `music_web` (generation flow)
- **Preconditions:**
  - User has 100 credits
  - Lyrics generation costs 2 credits (hypothetical, verify actual cost)
- **Steps:**
  1. Generate lyrics only (not full song)
  2. Check wallet balance
- **Expected:**
  - Balance: 100 → 98 (2 credits deducted)
  - Transaction log: "lyrics_generation" debit
- **Failure Meaning:** Lyrics cost not implemented or wrong amount

---

### Category L: Two Ledgers (Web vs Desktop)

#### TC-L01: Web ledger uses integer credits

- **Surface:** `music_web`, `user_portal` (API calls)
- **Preconditions:**
  - User generates song via music_web
- **Steps:**
  1. Inspect API request/response
  2. Check transaction log
- **Expected:**
  - Credits are integers: `10`, `100`, `1000` (not `10.0000` or micro-units)
- **Failure Meaning:** Web using wrong credit unit format

---

#### TC-L02: Desktop ledger uses micro-units

- **Surface:** `camxora` (desktop app)
- **Preconditions:**
  - User generates song via desktop app
- **Steps:**
  1. Inspect desktop API calls
  2. Check transaction log
- **Expected:**
  - Credits may be in micro-units: `100000` = 10 credits (if 10,000 micro-units per credit)
  - Backend converts correctly
- **Failure Meaning:** Desktop using wrong unit; transaction mismatch risk

---

#### TC-L03: One charge model enforced (flag ON)

- **Surface:** `platform_api` (charge service)
- **Preconditions:**
  - `credits_only_v3_charge` flag ON
  - User generates song from desktop AND web
- **Steps:**
  1. Generate 1 song from desktop (10 credits)
  2. Generate 1 song from web (10 credits)
  3. Check wallet balance
- **Expected:**
  - Both charges use same credit amount: 10 credits each
  - Wallet deducted consistently across surfaces
- **Failure Meaning:** Charge amounts inconsistent between surfaces

---

## Critical Edge Cases

### EC-01: User with 0 wallet + expired grant cannot generate

- **Surface:** `platform_api`
- **Preconditions:**
  - User wallet = 0
  - Monthly grant = 0 (expired subscription)
  - `credits_only_v3_charge` flag ON
- **Steps:**
  1. Attempt song generation
- **Expected:** HTTP 402 Insufficient Credits
- **Failure Meaning:** Free API abuse possible

---

### EC-02: Free plan user at daily cap cannot generate until reset

- **Surface:** `platform_api`
- **Preconditions:**
  - User on Free plan (50 daily credits)
  - User consumed all 50 credits today
  - Daily reset not yet occurred
- **Steps:**
  1. Attempt song generation (10 credits)
- **Expected:**
  - HTTP 402 or 429 "Daily limit reached"
  - Error message: "Try again after midnight UTC"
- **Failure Meaning:** Daily cap not enforced

---

### EC-03: Conversion run twice for same user fails

- **Surface:** `platform_api` (conversion service)
- **Preconditions:**
  - User already converted once
  - Conversion marked complete in DB
- **Steps:**
  1. Attempt conversion again
- **Expected:**
  - Error: "Conversion already completed for this user"
  - No additional credits minted
- **Failure Meaning:** Double-conversion possible; critical bug

---

### EC-04: $79 hidden plan auto-renew still works

- **Surface:** `platform_api` (subscription renewal)
- **Preconditions:**
  - Existing user on $79 plan
  - Auto-renew enabled
  - Renewal date reached
- **Steps:**
  1. Wait for renewal date
  2. Check subscription status
- **Expected:**
  - Renewal processes successfully
  - $79 charged
  - 3000 credits granted
  - Plan remains `is_public=false`
- **Failure Meaning:** Hidden plan renewals broken; existing customer impact

---

## Risk Assessment

### High Risk Areas

1. **Hidden $79 Plan Leakage:**
   - If `is_public=false` filter fails, legacy plan appears on public pages
   - Impact: Brand confusion, pricing inconsistency
   - Mitigation: Test all public surfaces (website, music_web, user_portal)

2. **Conversion Double-Mint:**
   - If conversion idempotency check fails, users can mint credits multiple times
   - Impact: Financial loss, credit inflation
   - Mitigation: Test EC-03 thoroughly; add DB constraint

3. **Free API Abuse:**
   - If 402 check missing, users with 0 credits can generate unlimited songs
   - Impact: Suno API cost explosion
   - Mitigation: Test TC-C04, EC-01, EC-02

4. **Dual-Channel Credit Multiplication:**
   - If profile pack logic grants credits instead of slots
   - Impact: Product confusion, revenue leakage
   - Mitigation: Test TC-H01, TC-H02

5. **Legacy Quota System Still Active:**
   - If credits-only flag OFF still allows quota-based charging
   - Impact: Inconsistent billing, user confusion
   - Mitigation: Test both flag states

### Medium Risk Areas

1. **Song Hint Calculation Wrong:**
   - If showing "x2 for dual-channel" or incorrect math
   - Impact: User expectation mismatch
   - Mitigation: Test TC-H03, TC-J02

2. **Refund Logic Missing:**
   - If generation fails but credits not refunded
   - Impact: User dissatisfaction, support tickets
   - Mitigation: Test TC-C05

3. **Daily Grant Stacking:**
   - If daily grants stack indefinitely (no cap)
   - Impact: Free users accumulate unlimited credits
   - Mitigation: Test TC-D01 with multi-day simulation

### Low Risk Areas (but must test)

1. **Admin UI Legacy References:**
   - Old "quota" terminology in admin portal
   - Impact: Internal confusion only
   - Mitigation: Test Category B cases

2. **Ledger Unit Mismatch:**
   - Web vs desktop micro-unit handling
   - Impact: Display bugs, not charge bugs (if backend converts correctly)
   - Mitigation: Test TC-L01, TC-L02, TC-L03

---

## Regression Test Checklist

After implementing credits-only v3, verify these still work:

- [ ] User registration flow (email verification)
- [ ] Login/logout (JWT refresh tokens)
- [ ] Password reset flow
- [ ] Existing Lifetime license users unaffected
- [ ] Suno callback webhook processing
- [ ] Admin user management (suspend/reactivate)
- [ ] Profile creation/deletion (within slot limits)
- [ ] Batch generation (multiple songs)
- [ ] Image generation (if using credits)
- [ ] Draft generation (if using credits)
- [ ] WebSocket notifications
- [ ] Rate limiting (429 responses)
- [ ] Health check endpoint (`/health`)

---

## Test Execution Priority

### Phase 1: Smoke Tests (Run First)
- TC-A01, TC-A03, TC-B01, TC-C01, TC-C04, EC-01

### Phase 2: Core Billing Logic
- TC-C02, TC-C03, TC-C05, TC-D01, TC-E01, TC-E02

### Phase 3: Conversion Logic
- TC-F01 through TC-F06, EC-03

### Phase 4: UI Surfaces
- All Category A, J, K tests

### Phase 5: Edge Cases & Regression
- All EC-* tests, regression checklist

---

## Notes for Test Execution

1. **Sandbox vs Local:**
   - Run API tests locally first (faster iteration)
   - Run UI tests on sandbox (closer to production)
   - Production is **read-only** for verification only

2. **Flag State:**
   - Test critical paths with `credits_only_v3_charge` both ON and OFF
   - Verify graceful degradation when flag OFF

3. **Data Cleanup:**
   - After conversion tests, reset test user data
   - Mark conversion as incomplete to re-test

4. **Automation:**
   - Prioritize automating Category C (API) tests with pytest
   - UI tests can be manual for first pass
   - Consider Playwright for music_web/website tests

5. **Documentation:**
   - Update API docs with v3 endpoints
   - Update user-facing help articles with credits terminology
   - Archive legacy quota system docs

---

## Test Completion Criteria

- [ ] All TC-* tests pass
- [ ] All EC-* edge cases handled gracefully
- [ ] Zero hidden plan leaks on public surfaces
- [ ] Conversion dry-run safe (no DB changes)
- [ ] $79 plan renewals still work
- [ ] Free plan daily grants work
- [ ] 402 errors prevent zero-balance generation
- [ ] Desktop app shows credits (not quota)
- [ ] Admin portal has credits catalog (not quota editor)
- [ ] Dual-channel packs do NOT add credits
- [ ] Regression checklist all green

---

## Follow-Up Actions After Testing

1. **If critical bugs found:**
   - Block sandbox deploy until fixed
   - Re-run failed tests after fix

2. **If minor bugs found:**
   - Log as issues
   - Assess production impact
   - Schedule fix before or after deploy

3. **Documentation updates:**
   - API changelog for v3 endpoints
   - User guide: "Understanding Credits"
   - Admin guide: "Managing Plans & Credits"

4. **Production deploy checklist:**
   - [ ] All tests pass on sandbox
   - [ ] Conversion script tested on anonymized prod data copy
   - [ ] Rollback plan documented
   - [ ] Support team briefed on credits system
   - [ ] Monitoring alerts configured for 402 errors
   - [ ] `credits_only_v3_charge` flag ready to flip (but do NOT flip per requirements)

---

**End of Test Matrix**
