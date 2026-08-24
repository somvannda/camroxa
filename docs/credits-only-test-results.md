# Credits-only test results (sandbox)

**Date:** 2026-08-23 00:25 ICT (UTC+7); visual login pass 2026-08-23 ~08:05 ICT; B03 user-detail 2026-08-23 ~08:25 ICT  
**Host:** api.sandbox.camxora.com / 46.250.235.83 only  
**Production:** not touched  
**Conversion apply:** SKIPPED (dry-run mintable=0)  
**Flag `credits_only_v3_charge`:** left **Off** (visual/public re-run only)  
**Final flag state:** `false`
**This follow-up:** 2026-08-23 ~09:40 ICT desktop logged-in G01-G03/L02 (existing PID 86800 Camxora; no password typed; no Generate click).
**Prior desktop:** 2026-08-23 ~08:46 ICT G01-G03 still login-blocked; 08:55 API leftover.

**Prior API smoke:** `scripts/deploy/_credits_only_sandbox_api_smoke.py` (20/20 PASS).  
**This pass:** public/visual re-run after sandbox UI went live. No conversion apply. No production.

## Counts

| Result | Count |
|--------|------:|
| PASS | 45 |
| FAIL | 0 (matrix); 1 local pytest (unchanged) |
| BLOCKED | 7 |
| SKIP (apply) | 1 |

Visual/public deltas: **A03, A04, J01, J02, K01** BLOCKED to PASS.
Logged-in Chrome deltas: **B01, B02, B03, B04** BLOCKED to PASS. Leftover: music Free card 50 (was 0). **K02** PASS (Create wired to lyric_credits=5; deployed). **H04-H09** PASS-unit (6 pytest, no live addon buy). **A05/I02** portal not past email/login. Desktop **G01, G02, G03, L02** BLOCKED to PASS (logged-in Studio). Wallet chrome: **1,060.0 credits**. Shot: docs/test-shots/desktop-credits-loggedin.png.

**2026-08-23 ~08:55 ICT leftover (API-only):** Reconfirmed public v1+v3 (api + music proxy): 7 rows, no $79/7900, yearly monthly_credits equals monthly (1000/3500/8000), Free daily_credits=50, v3 lyric_credits=5 music_credits=10. **A07** 50 concurrent public GETs, 0 leaks. **Yearly catalog** PASS (not live checkout). **I03 public-filter** PASS. **H04-H09** reconfirmed 6 pytest + 4 billing-period unit tests (10 passed). **C03** left BLOCKED-live-gen (no Suno). **E03** still BLOCKED-live; period math unit-proven (`test_billing_period_service.py` 4 passed; grant-period endpoint exists from prior smoke). **A05/I02** still email-confirm (shot portal-onboarding-leftover.png). Flag not flipped; remains Off. No conversion apply. No new Studio window.


## Results

| ID | result | notes |
|----|--------|-------|
| TC-A01 | PASS | Reconfirmed 2026-08-23 ~08:55 ICT. GET https://api.sandbox.camxora.com/api/v1/plans/public 200, 7 rows: Free + starter/creator/studio monthly+yearly. No $79 / 2-channel / 7900. Prices 1000/3000/6000 + yearly 10200/30600/61200; credits 1000/3500/8000 (yearly same as monthly). Free daily_credits=50. music.sandbox proxy same. |
| TC-A02 | PASS | Reconfirmed 2026-08-23 ~08:55 ICT. GET /api/v3/plans/public 200 (api + music). 7 rows all is_public=true is_active=true; no 7900. Free daily=50 lyric=5 music=10. Yearly monthly_credits match monthly. |
| TC-A03 | PASS | https://sandbox.camxora.com/pricing 200. SSR cards: Free $0, Starter $10 / 1,000 credits, Creator $30 / 3,500, Studio $60 / 8,000. No 2-channel card. $79 only in footnote: Hidden $79 desktop rows stay off this page. Free card shows 50 daily credits from v1 public daily_credits. |
| TC-A04 | PASS | https://music.sandbox.camxora.com/pricing 200. After music_web overlay of /api/v1|/api/v3 plans/public, Free card DOM is 50 daily credits (was 0 from v2 subscriptions/plans). Shot: docs/test-shots/music-pricing-free50.png |
| TC-A05 | BLOCKED | 2026-08-23 ~08:55 ICT: existing Chrome tab https://app.sandbox.camxora.com/onboarding still Confirm your email / 6-digit code. Not past email confirm. No $79 cards. Shot: docs/test-shots/portal-onboarding-leftover.png (also portal-onboarding.png). |
| TC-A07 | PASS | 50 concurrent GET /api/v1|/api/v3 plans/public (20 workers). 50 ok, 0 leak of 7900 / 2-channel / is_public=false. |
| TC-B01 | PASS | Logged in duke@camxora.com SANDBOX. /plans = Credits-only billing. Debit Generate via v3 Off. Rows: Free $0 public 50 cr/day; starter/creator/studio monthly $10/$30/$60 public; yearly public; Monthly 2-channel $79 Hidden; add-on channel SKUs Hidden. Actions: Edit credits only (no quota/channel/web-music editors). Shot: docs/test-shots/admin-sandbox-plans.png |
| TC-B02 | PASS | Same /plans catalog is credits-only (Free + starter/creator/studio + hidden $79 + hidden add-ons). No quota/channel/web-music editors on the list. Shot: docs/test-shots/admin-sandbox-plans.png |
| TC-B03 | PASS | User-detail pages (not list-only). duke 40fa8090: wallet 122.5, period grant remaining 0, Adjust wallet; copy Quota meters and quota top-up are retired. Kong 25d7efb2: Credit Balance 0.08 wallet / grant remaining 0 / 74 burned, starter_monthly. No quota top-up editor, no song-draft meters editor. Shots: docs/test-shots/admin-user-duke.png, admin-user-kong.png |
| TC-B04 | PASS | /usage = Credit usage and transactions; wallet charged 97.5, refunds, net wallet. /finance = Profit and revenue estimate; wallet charged revenue 0.975 USD (97.5 credits). Not song/draft quota meters. Shots: docs/test-shots/admin-usage.png, admin-finance.png |
| TC-C01 | PASS | Prior smoke quote (unchanged). |
| TC-C02 | PASS | Prior smoke charge (unchanged). Did not call live song. |
| TC-C03 | BLOCKED | BLOCKED-live-gen. No dry quote-only live-Suno path used. Did not spend real Suno. Quote/charge 10 already smoked (C01/C02). |
| TC-C04 | PASS | Prior 402 INSUFFICIENT_CREDITS (unchanged). |
| TC-C05 | PASS | Prior refund smoke (unchanged). |
| TC-C06 | PASS | Prior wallet GETs (unchanged). |
| TC-D01 | PASS | v3 public Free daily_credits=50 (reconfirmed). |
| TC-D02 | PASS | Free plan present on v3 public with daily_credits. |
| TC-E01 | PASS | Prior grant-period smoke (unchanged). |
| TC-E02 | PASS | Prior dry-run leftover (unchanged). |
| TC-E03 | BLOCKED | Live month rollover not faked. Proven: `period_start_for_subscription` / `compute_billing_period` unit tests (4 passed: 90-day roll, 30-day align, calendar fallback). POST /api/v3/admin/billing/grant-period exists (`ensure_period_grant`: already_granted vs grant monthly_credits; expires unused lots). Prior smoke called grant-period. No live cycle advance. |
| TC-F01 | PASS | Prior conversion dry-run (unchanged). |
| TC-F02 | PASS | Apply with confirm=false rejected; apply not run. |
| TC-F03 | PASS | mintable leftover 0. |
| TC-F04 | PASS | Both licenses expired, mint 0. |
| TC-F05 | PASS | lifetime_skipped=0. |
| TC-F06 | PASS | Dry-run minted 0. |
| TC-F07 | PASS | 2 expired licenses, 0 mintable. |
| TC-F08 | SKIP | Apply skipped. |
| TC-G01 | PASS | 2026-08-23 ~09:40 ICT. Existing PID 86800, title Camxora, not login. Sidebar + footer wallet: **1,060.0 credits**. Also CREDITS card: Credits balance 1,060.0 credits. Account Somvannda Kong / Free plan. Footer Ready: Dashboard / Sandbox API / v1.3.1. Did not type password. Shot: docs/test-shots/desktop-credits-loggedin.png |
| TC-G02 | PASS | Music page (no Generate click): button **Generate (12.1001 Credits)**; strip Draft: 0.6001 credits / Suno: 7.5 credits / Image: 1 credits; summary Total 12.1001 credits. Dashboard CREDITS copy: One wallet number. Generate still works the same; leftover package counts are not shown as a plan. No Plan quota on Generate. |
| TC-G03 | PASS | Balance chrome is a single credits number (1,060.0 credits), not Plan quota / song-draft-image meters. CURRENT PLAN shows No plan / Expiration not provided. Credits Spent 40 is a usage tile, not the wallet. No Plan quota string in UIA. |
| TC-G04 | BLOCKED | Desktop v3 network. See morning command below. |
| TC-H01 | BLOCKED | $5 addon checkout not executed. |
| TC-H02 | BLOCKED | $10 addon checkout not executed. |
| TC-H03 | PASS | Public song hint floor(credits/10): 1000->100, 3500->350, 8000->800. Website SSR shows ~100 / ~350 / ~800 songs/mo. |
| TC-H04 | PASS | Existing sandbox license somvannda@gmail.com has profile_addon_slots=8 vs sommakara 0. Same plan monthly/daily meter columns. Remote resolve_effective_entitlements(0 vs 8): song/draft/image/video/merge unchanged (300/100000/1200/3000/3000). quota_channels 2 vs 10 only. No purchase. |
| TC-H05 | PASS | Draft monthly limit identical at 0 and 8 addon slots (100000). |
| TC-H06 | PASS | Image monthly limit identical (1200). |
| TC-H07 | PASS | Video monthly limit identical (3000). Daily video 1000 vs 1000. |
| TC-H08 | PASS | Merge monthly limit identical (3000). Daily merge unchanged. |
| TC-H09 | PASS | H04-H08: meters do not scale with existing addon slots. No $5/$10 buy. Existing unit tests cover the same asserts. |
| TC-I01 | PASS | Prior admin API hidden $79 row (unchanged). |
| TC-I02 | BLOCKED | Same as A05 leftover: portal still email-confirm. No $79 cards. Shot: portal-onboarding-leftover.png |
| TC-I03 | PASS | Hidden 7900 not on v1/v3 public (api + music). Catalog yearly/monthly public only. Admin hidden row already I01. |
| TC-J-yearly-catalog | PASS | Public catalog: starter/creator/studio yearly monthly_credits 1000/3500/8000 equal monthly. Cash 10200/30600/61200 (15% off 12x monthly, not matrix $100/$300/$600). No live yearly checkout. |
| TC-J01 | PASS | Website pricing: four article cards only (Free + Starter + Creator + Studio). No 2-channel card. No $79 card. |
| TC-J02 | PASS | Dual-channel is a bullet (Dual channels) on every card plus copy: Dual-channel desktop is included on every paid plan - it is not a separate SKU. |
| TC-K01 | PASS | Music pricing uses public plans + hard filter price_cents>0 && 7900!==e.price_cents plus Free finder. |
| TC-K02 | PASS | Logged-in /create 2026-08-23 ~08:35 ICT. Button text: Create â€¢ 10 credits. Lyrics â€¢ 5 credits; Auto-generate â€¢ 5 credits. Wallet 1,726 / 1,800 (includes 800 top-up). Shot: docs/test-shots/music-create-lyric.png. No Suno generate. Overlay+labels deployed earlier this morning (subscription-api.ts, create-page-client.tsx; camxora-music rebuilt). Free card shot docs/test-shots/music-pricing-free.png = 50 daily credits. |
| TC-L01 | PASS | Web/v3 wallet balance_credits (unchanged). |
| TC-L02 | PASS | Desktop ledger/wallet looks like **credits**, not micro-units: chrome 1,060.0 credits; Music estimate 12.1001 / 0.6001 / 7.5 credits. Not a 6-digit micro balance. |
| TC-L03 | PASS | Prior flag-ON charge then restored OFF. Flag still OFF. |

## Local pytest

Matrix-adjacent: 25 PASS, 1 FAIL test_v3_routes_and_v1_public_shape_unchanged (serializer now includes monthly_credits). This leftover: platform_api/tests/test_subscription_entitlement_service.py **6 passed** + test_billing_period_service.py **4 passed** (10 total; PYTHONPATH=worktree). Addon slots do not scale meters. Period math unit-proven. No platform_api/.venv in this worktree.

## Public plans assertion

GET /api/v1/plans/public and GET /api/v3/plans/public (api.sandbox + music.sandbox proxy):

- $79 / Monthly 2-channel hidden
- Starter / Creator / Studio present (starter_monthly $10 / 1000; creator_monthly $30 / 3500; studio_monthly $60 / 8000)
- Yearly SKUs public
- Free on v1 and v3: daily_credits=50
## Website / music / admin / portal evidence

- Website SSR: Free $0 / 50 daily credits, Starter $10 / 1,000, Creator $30 / 3,500, Studio $60 / 8,000. Footnote only for $79.
- Music: https://music.sandbox.camxora.com/pricing 200; GET https://music.sandbox.camxora.com/api/v3/plans/public 200; JS filter 7900!==e.price_cents
- Admin logged-in: https://admin.sandbox.camxora.com/plans credits-only catalog, Generate v3 Off, Hidden. /users list + user-detail wallet/grant (duke, Kong). /usage + /finance wallet-centric.
- Portal: /onboarding email confirm; /dashboard login. Music pricing 2026-08-23 ~08:35 ICT: Free still 50 daily credits (resets at midnight). Shot: docs/test-shots/music-pricing-free50.png. Logged-in /create: Create â€¢ 10 credits. Shot: docs/test-shots/music-create-lyric.png.

## Flag note
Left OFF. This follow-up did not flip credits_only_v3_charge. Music pricing + create display only; no API restart required for the overlay.
## ASK_CURSOR
1. music_web host is music.sandbox.camxora.com
2. Desktop needs GUI; see camxora_python/.env.sandbox.example
3. Admin session OK on earlier B03 shots (duke/Kong wallet-grant). This leftover new Chrome window hit admin login + music /create login. Portal still email-confirm/login. Desktop Studio not launched; remaining_month_card.py is credits wallet only.
4. Free card daily credits 0 vs API 50? Fixed: v1 public now returns daily_credits=50; website Free card shows 50.
5. platform_api venv path?

## Desktop morning command
Not launched (would steal GUI session). Inspected remaining_month_card.py: CREDITS wallet + spent this month; no plan meters. If launching later:
   cd /d D:\\Development\\Projects\\Electron\\MusicGenerator-credits-only-api-v3\\camxora_python
   copy .env.sandbox.example .env if needed
   python main.py
Host api.sandbox.camxora.com/api/v1.


## ASK_CURSOR
1. Music /create in a new Chrome tab hit login; need a logged-in Create shot of `Create Â· 5 credits` if you want visual K02 proof.
2. Desktop G01-G03 + L02 PASS 2026-08-23 ~09:40 ICT. Wallet **1,060.0 credits**. Shot docs/test-shots/desktop-credits-loggedin.png. Did not click Generate.
   Host: https://api.sandbox.camxora.com/api/v1
3. Portal A05/I02 still email-confirm / dashboard login.

## Desktop G01-G03 recheck (2026-08-23 ~08:50 ICT)
Did not start a second instance. Existing process PID 86800: python ...\camxora_python\run_entry.py. Window title **Camxora**. Still login (Welcome back / Sign in). Re-saved docs/test-shots/desktop-credits.png (1920x1080). No password typed. G01-G03 remain BLOCKED. Production .env not touched.


## Leftover 08:55 ICT (API-only, no GUI login)

- Flag `credits_only_v3_charge` not flipped; left Off.
- No new Studio window. Existing Camxora PID 86800 still login.
- No production. No conversion apply. No Suno generate.
- New PASS: A07, I03 public-filter, J-yearly-catalog (counts 38 -> 41).
- Still needs him at the machine: A05/I02 email code; G04 desktop v3 network; H01/H02 addon checkout; C03 live Suno if ever required; E03 live billing-cycle advance. G01-G03/L02 done (no Generate spend).

## Desktop G01-G03/L02 logged-in (2026-08-23 ~09:40 ICT)

Existing python Camxora PID 86800 brought to front (maximized). Already signed in as Somvannda Kong. No password. No Generate click. No production. Flag left Off.

- Exact credit text: sidebar/footer **1,060.0 credits**; CREDITS card **Credits balance** / **1,060.0 credits**; Music **Generate (12.1001 Credits)** / **Draft: 0.6001 credits / Suno: 7.5 credits / Image: 1 credits** / **Total 12.1001 credits**.
- G01 PASS, G02 PASS, G03 PASS, L02 PASS (credits not micro-units).
- Shot: docs/test-shots/desktop-credits-loggedin.png
- Counts 41 PASS / 11 BLOCKED -> **45 PASS / 7 BLOCKED**.
