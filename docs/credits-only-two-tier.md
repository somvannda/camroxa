# Credits-only, two-tier model (Free / Pro)

**Status:** approved 2026-10-30 · **Supersedes:** plans, subscriptions, plan quotas, profile add-ons
**Applies to:** camxora.com, desktop (camxora_python), platform_api, admin_portal

---

## 1. Decision

CAMXORA has exactly **two tiers**:

| Tier | Definition |
|---|---|
| **Free** | No live credit pack. |
| **Pro** | At least one live (unexpired, non-zero) credit pack. |

There are **no plans, no subscriptions, no monthly quotas, no add-ons, and no profile limits**.
Every user must buy a credit pack to generate. When a Pro user's pack credits expire or reach
zero, they become Free automatically. Buying again makes them Pro again.

---

## 2. Definitions

| Term | Meaning |
|---|---|
| **Credit** | Spend unit. Stored as micro-units: `1 credit = 10,000 units`. |
| **Wallet** | `credit_wallets.balance` — the single spendable number. |
| **Lot** | A row in `credit_wallet_lots`: `tag`, `amount_units`, `remaining_units`, `expires_at`. |
| **Pack lot** | `tag='pack'` — credits bought with money. 30-day expiry. |
| **Admin lot** | `tag='admin'` - manual support credit. **30-day expiry**, same as a pack. Never grants Pro. |
| **Live** | `remaining_units > 0 AND (expires_at IS NULL OR expires_at > now())`. |
| **Tier** | Derived from pack lots. Never stored or edited by hand. |

---

## 3. Rules

### Tier

- **R1** — A user is **Pro** if and only if they have at least one live pack lot.
- **R2** — Every other user is **Free**.
- **R3** — Tier is derived at read time from `credit_wallet_lots`. There is no editable tier column.
- **R4** — Tier changes take effect immediately: a purchase makes Pro; expiry/zero makes Free.
- **R5** — Admin lots and referrals never grant Pro.

### Credits

- **R6** — `credit_wallets.balance` must equal the sum of live lot `remaining_units`.
- **R7** — Every spend decrements the lots it consumed. The wallet total is updated in the same transaction.
- **R8** — Spend order is **earliest expiry first**, then oldest `created_at`.
- **R9** — Pack credits expire **30 days after purchase**.
- **R10** — Buying a new pack extends the expiry of all live pack lots to the new date (single wallet expiry).
- **R11** — New accounts receive **50 trial credits once** (tag `grant`, no expiry). There are no daily or monthly grants after that.
- **R12** — A refund reverses the pack lot. If it was the user's only live pack, the user becomes Free.
- **R13** — An expired lot is zeroed by the sweep; its credits are gone and cannot be restored except by a new purchase or an admin lot.

### Access

- **R14** — **Free**: web only. Browse, preview, and generate while the 50 trial credits last. No desktop studio.
- **R15** — **Pro**: desktop + web, all generation while `balance >= operation cost`.
- **R16** — **Pro with insufficient balance**: library, history, and re-download of owned files. Generation is blocked until top-up.
- **R17** — Downloading or playing content the user already owns is never blocked by tier or balance.
- **R18** — Admin/staff accounts bypass the tier gate.
- **R19** — Suspended/deleted accounts are blocked independently of tier.

### Profiles

- **R20** — Channel profiles are **unlimited**. No allowance, no add-on slots, no purchase.

### Pricing

- **R21** — Operation prices come only from the `pricing` table. No plan pricing.
- **R22** — Every charge is a wallet debit recorded in `credit_transactions` with `reason='v3_<op>'`.

---

## 4. Capability matrix

| Capability | Free | Pro (credits ≥ cost) | Pro (credits < cost) |
|---|:--:|:--:|:--:|
| Sign in / browse | ✅ | ✅ | ✅ |
| Preview tracks | ✅ | ✅ | ✅ |
| View library & history | ✅ | ✅ | ✅ |
| Re-download owned files | ✅ | ✅ | ✅ |
| Generate songs / images / drafts | ❌ | ✅ | ❌ |
| Export video / merge | ❌ | ✅ | ❌ |
| Desktop studio | ❌ | ✅ | ✅ (read-only) |
| Buy a pack | ✅ | ✅ | ✅ |
| Unlimited profiles | ✅ | ✅ | ✅ |

---

## 5. Credit lifecycle

```
Purchase pack
   └─ create pack lot (30d) ──► tier = Pro
        └─ spend (FIFO by expiry) ──► balance ↓
             ├─ balance ≥ cost ──► generate
             └─ balance < cost ──► blocked, top-up prompt
        └─ expiry sweep ──► lot = 0 ──► tier = Free
Refund
   └─ reverse lot ──► if no live pack left, tier = Free
Admin adjustment
   └─ admin lot (30 days) ──► spendable, tier unchanged
```

**Invariant to enforce in code and tests:**

```
balance == SUM(remaining_units) over live lots
tier == 'pro' <=> EXISTS(live pack lot)
```

---

## 6. Cutover (production, 2026-10-30)

Conversion rule: **one pack lot per user, equal to their current wallet balance**, expiry =
the user's **original** plan/subscription expiry. No invented dates. Users whose plan already
expired are reset to **Free with 50 credits**. All other lots are zeroed so the wallet invariant
holds.

| User | Credits | Tier | Until |
|---|---:|---|---|
| sophay@camxora.com | 8,658.95 | Pro | 2026-11-01 |
| mr.zhiwei@gmail.com | 5,009.85 | Pro | 2026-11-01 |
| edmbass1@gmail.com | 2,676.43 | Pro | 2026-11-03 |
| tepchanpanharith@gmail.com | 0.11 | Pro | 2026-11-06 |
| iamduke1987@gmail.com | 886.00 | Pro | 2026-11-05 |
| mr.limeang.018@gmail.com | 520.00 | Pro | 2026-11-12 |
| pich.sou11@gmail.com | 50.00 | Free | — (sub expired 2026-10-03) |
| teangchunpanhavorn@gmail.com | 50.00 | Free | — (sub expired 2026-10-06) |

| Group | Count | Action |
|---|---:|---|
| 6 active plan/sub users | 6 | **Pro** until original expiry, keep wallet |
| 2 expired plan/sub users | 2 | **Free** with 50 credits |
| Other pack buyers | 5 | Unchanged (already Pro) |
| Free users | 224 | Keep signup credits as one `grant` lot; remain **Free** |
| DistroKid entitlements | — | **Preserve** on `users` before dropping `licenses` |

**On expiry:** Pro → Free and the remaining credits are **kept** in a non-expiring `legacy` lot
(`ref_id='legacy_conversion_2026_10_30'`). Only the two already-expired users are reset to 50.

---

## 7. Removed concepts

- `plans`, `licenses`, `plan_usage`, `plan_offers`, `web_subscriptions`, `user_period_quota_topups`
- Monthly song/image/draft/video/merge quotas and top-ups
- `daily_quota_bank`
- Profile allowance and profile add-ons
- Plan checkout, renewals, plan changes, plan discounts
- Free daily/monthly grants

---

## 8. Non-goals

- No free trial tier.
- No grandfathering beyond the cutover conversion in §6.
- No per-plan pricing or discounts.
- No changes to the `pricing` table or per-operation costs.
