# Mail templates — which run automatically, which need a human

Two stacks, one policy. "Automatic" means an automation in `mail_automations`
evaluates the trigger on a schedule. "Manual" means the template is only usable
from a campaign, because sending it on a timer is either wrong or unfair.

Enforced in code as `mail_templates.send_mode`:

| send_mode | Meaning |
|---|---|
| `auto` | may be attached to an automation **and** used in a campaign |
| `manual` | campaigns only; the automation form refuses it |

Discount and seasonal are `manual` because:
- a discount must be priced, scoped and capped by a human each time;
- a seasonal message tied to a holiday date is wrong the day after, and an
  automation that keeps firing it is worse than not sending it.

## Matrix

| # | Template | Platform (`camxora_platform`) | musicapi (`sunoapi`) | Mode | Trigger / audience |
|---|---|---|---|---|---|
| 01 | Welcome | ✅ | ✅ | **auto** | `signup`, delay 30m |
| 02 | Signed up, never generated | ✅ | ✅ | **auto** | no generation after 3d |
| 03 | Pack ladder | ✅ | ✅ | **manual** | campaign: active, never paid |
| 04 | Discount | ✅ | ✅ | **manual** | campaign: targeted, one code per recipient |
| 05 | Low balance | ✅ | ✅ | **auto** | balance < user threshold |
| 06 | Win-back | ✅ | ✅ | **auto** | inactive 30d |
| 07 | Receipt | ✅ | ✅ | **auto** | payment `paid` (transactional) |
| 08 | Payment expired | ✅ | ✅ | **auto** | checkout expired / abandoned |
| 09 | Credits expiring | ✅ | ✅ | **auto** | credit batch expires in ≤5d |
| 10 | Referral | ✅ | ✅ | **manual** | campaign: active payers |
| 11 | Stems spotlight | ✅ | ✅ | **manual** | campaign: active, has used stems=0 |
| 12 | Seasonal | ✅ | ✅ | **manual** | campaign only, dated offer |

Every template can also be sent **manually to one address** from the console
(the Test action), which is how you should proof every change before a campaign.

## What each stack must supply

Same template file, different variables — the renderer merges a shared set with
whatever the stack's query returns.

| Variable | Platform source | musicapi source |
|---|---|---|
| `first_name` | `users.display_name` | `users.name` |
| `credits` | `credit_wallets.balance` | `SUM(api_keys.credits)` |
| `songs` | `credit_transactions` where `direction='debit'` and reason = generate | `usage_logs` endpoint `music` |
| `packs_html` | `credit_packs` (price_cents, total_credits) | `credit_packs` (price, amount) |
| `best_pack_*` | derived from the above | derived from the above |
| `code` | existing `redeem_codes` row | `promo_codes` row |
| `referral_code` | `users.referral_code` | invite code |
| `expiring_credits` | `credit_wallet_lots` where `expires_at` ≤ 5d | credit lots with expiry |
| `pack_name` / `amount_paid` | `billing_payments` + `credit_packs` | `payment_transactions` + `credit_packs` |

## Trigger queries per stack

**Platform**
- `payment_expired`: `billing_payments.status = 'expired'`, one send per `reference_id`.
- `credits_expiring`: `credit_wallet_lots.expires_at` within N days and `remaining_units > 0`.
- `low_balance`: `credit_wallets.balance <` the user's threshold, paid users only.
- `inactive`: `GREATEST(last_active_at, last credit_transaction) < now() - 30d`.

**musicapi**
- `payment_expired`: `payment_transactions.status IN ('pending','expired')` older than 10 minutes.
- `credits_expiring`: `api_keys.credit_expires_at` within N days.
- `low_balance`: pooled `SUM(api_keys.credits)` below the user's `credit_alert_thresholds`.
- `inactive`: `user_value.last_seen_at < now() - 30d`.

## Guards that apply to every automatic send

1. **Suppression list** — hard bounce, complaint or unsubscribe blocks everything.
2. **Consent** — `email_subscription = true` for marketing; transactional ignores it.
3. **Cooldown** — no two marketing mails inside 7 days, across campaigns *and*
   automations.
4. **Per-journey cooldown** — win-back monthly, low-balance weekly, welcome and
   never-generated effectively once.
5. **Idempotency** — a dedupe key per (journey, user, window); a retried run or a
   second worker cannot double-send.
6. **Price integrity** — a discount never reaches anyone who paid full price in
   the last 14 days.

## Redeem codes

- **Platform:** `admin.camxora.com/redeem-codes` already exists and already
  supports `discount_percentage`, `discount_amount` and `credit_grant`. Campaigns
  reference it — mail only generates and embeds the code, redemption stays where
  it is.
- **musicapi:** the equivalent is **Mail → Promo Codes**
  (`admin.musicapi.camxora.com/admin/mail/promos`), which supports percent and
  bonus-credit codes, per-recipient single-use codes, and redeems inside the
  ChmabaPay checkout transaction. If parity of naming matters, add a
  `/admin/redeem-codes` nav alias pointing at the same page — the backend does
  not need to change.

Discount campaigns on either stack: the console creates one code per recipient at
send time, bound to that user, single use. A forwarded email cannot be redeemed
by anyone else.
