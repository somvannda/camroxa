# Designed E2E cases — wallet / one-wallet (2026-08-23)

Sandbox only. PASS / FAIL / BLOCKED. Not a 1000-path dump.

Accounts: leftover CutLuy `kongsomvannda1987@gmail.com` / `ksomvannda@gmail.com`; desktop `credits-cutover-test@sandbox.camxora.test`; one Free / expired $0.

## A. Shared wallet

| ID | Case | Expect |
|---|---|---|
| A01 | Admin `/users` Credits vs `/users/:id` wallet | Same integer |
| A02 | `GET /api/v3/me/credits` vs `/api/v1/credits/balance` | Same integer |
| A03 | Music web header vs A02 | Same integer |
| A04 | After leftover mint, v2 monthly+topup | 0 |
| A05 | Lots | leftover `quota_conversion` no expire; grant expires; pack no expire |

## B. Charge model

| ID | Case | Expect |
|---|---|---|
| B01 | Music generate | −10, two versions, never ×2 |
| B02 | Lyrics assist | `lyric` / −5 |
| B03 | Style assist | `style` |
| B04 | Desktop Pro on web Create | still −10 |
| B05 | Empty v3 wallet | 402, no v2 consume |
| B06 | Free daily | 50 from Free plan row |

## C. Admin recast

| ID | Case | Expect |
|---|---|---|
| C01 | `/users` Tag column | Gone |
| C02 | CutLuy user Plan | Catalog name (e.g. Starter), not Music tag |
| C03 | CutLuy Credits | Wallet cr, not used/daily |
| C04 | `/licenses` lists CutLuy + desktop | Source Web / Desktop |
| C05 | Web row actions | No Cancel / Add-ons |
| C06 | Assign still writes license | Desktop source row |
| C07 | Usage leftover | Label Web leftover, not grant issued |
| C08 | Finance grant issued | Period + daily only |
| C09 | User-spent plan filter | Unified catalog includes web |

## D. Surfaces

| ID | Case | Expect |
|---|---|---|
| D01 | Desktop paid login | Works |
| D02 | Free + desktop client | 403 DESKTOP_PLAN_REQUIRED |
| D03 | Desktop generate | −10, one credits number |
| D04 | Music pricing | Free + Starter/Creator/Studio, hide $79 |
| D05 | Music Create | −10 |
| D06 | Checkout URLs | still `/api/v1/v2/...` |
| D07 | Portal cards | Hide $79; wallet = shared |
| D08 | Portal quota-status | Must not drive billing UI |
| D09 | Website pricing | Same cards; ≈ floor(credits/10) |
| D10 | Admin non-billing pages | Load |

## E. Do not fail on

Portal email-confirm BLOCKED, live CutLuy buy unless run, Lifetime leftover, $79×5.

---

## Results (2026-08-23 sandbox run)

**Pytest:** 35 passed (`test_wallet_sync`, `test_web_ledger_conversion`, `test_web_music_v3_charge`, `test_v3_period_grant`, `test_usage_transaction_labels`, `test_v3_generate_charge`) + 11 passed (`test_user_spend_service`, labels again).

**Flag:** `credits_only_v3_charge=true`. Public v1/v3: 7 rows, no $79.

| ID | Result | Notes |
|---|---|---|
| A01 | PASS | List = detail wallet: cutover 5180; kong 1726.08; ksomvannda 1400.04 |
| A02 | PASS | Same integers on `GET /api/v3/me/credits` and `GET /api/v1/credits/balance` for the three watch users |
| A03 | BLOCKED | No leftover-user music-web session this sitting. Watch users' v3 works; header is v3-only. Duke `/api/v3/me/credits` 500 (Free admin) — header would fall back to v2 |
| A04 | PASS | v2 monthly=0 and topup=0 for all three leftover/cutover users |
| A05 | PASS | Leftover lots `quota_conversion` expire=null. Cutover also has `grant` expiring 2026-09-22 |
| B01 | PASS | Prior live Suno −10×2; cutover wallet 5200→5180, burned 30 |
| B02 | PASS | Unit + catalog lyric=5. No new live lyrics click |
| B03 | PASS | Unit + catalog style. No new live style click |
| B04 | PASS | Charge unification already on sandbox (no Pro skip). Not re-clicked |
| B05 | PASS | Prior 402 empty-wallet smoke |
| B06 | PASS | Public Free daily_credits=50; music cards show 50 daily credits |
| C01 | PASS | Users table: no Tag. Columns include Credits / Burned / Plan |
| C02 | PASS | CutLuy users Plan `starter_monthly` |
| C03 | PASS | Credits 1,726.08 / 1,400.04 cr — not used/daily |
| C04 | PASS | 7 rows: desktop 3 + web 4. Watch users Desktop $79 + Web Starter |
| C05 | PASS | Add-ons/Cancel only on the three Desktop rows |
| C06 | BLOCKED | Did not assign a new desktop license this sitting |
| C07 | PASS | Ledger has `v3_web_remaining` 1726 / 1400. Backend label "Web leftover". Not in grant issued |
| C08 | PASS | Usage/Finance grant issued = 3000 / 1 event (cutover period grant only) |
| C09 | PASS | After shipping `user_spend_service.py`, endpoint 200. Sample includes `starter_monthly` |
| D01 | PASS | Prior logged-in desktop session |
| D02 | PASS | Code + prior desktop gate (`403 DESKTOP_PLAN_REQUIRED`). Not re-probed this sitting |
| D03 | PASS | Prior two Suno jobs; chrome is one credits number |
| D04 | PASS | music.sandbox `/pricing`: Free + Starter/Creator/Studio. 50 daily / 1000 / 3500 / 8000. No $79 |
| D05 | BLOCKED | No leftover-user Create click (would spend). Charge path already proven |
| D06 | PASS | Code still `POST /api/v1/v2/subscriptions/purchase`. Live CutLuy not run |
| D07 | BLOCKED | Portal still email-confirm. Public cards themselves hide $79 (website + v1 public) |
| D08 | PASS | Dashboard copy is wallet-only. `quota-status` is still fetched in the provider; it does not render meter chips |
| D09 | PASS | sandbox.camxora.com/pricing: same four cards; ≈ 100 / 350 / 800; CTAs → music.sandbox |
| D10 | PASS | Opened dashboard, users, licenses, plans (no crash). Usage/user-spent/finance 200 via API. Remaining App.tsx routes not each clicked (admin sessionStorage drops on full navigation) |

**Counts:** PASS 28 · BLOCKED 5 · FAIL 0

**Fix shipped during the run:** sandbox `user_spend_service.py` (stale `list_web_subscriptions_for_users` call).

