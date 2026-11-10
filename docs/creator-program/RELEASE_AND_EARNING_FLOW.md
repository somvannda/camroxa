# Release & earning flow — recommendation

**Status:** Adopted for the Creator Program. Supersedes the pre-approval release model.
**Related:** [BRD](./BRD.md) · [Product Spec](./PRODUCT_SPEC.md) · [Technical Design](./TECHNICAL_DESIGN.md) · [UI System](./UI_SYSTEM.md)

---

## 1. Decisions

1. **Anyone can become a creator.** Claiming a page is instant. No application, no approval, no gate.
2. **Creators publish immediately.** A release goes live after automated checks. Moderation is post-publication, not pre-approval.
3. **Verification is an optional badge.** It signals trust and identity; it is not required to create, publish, or grow.
4. **Payouts require identity verification (KYC).** KYC is separate from the badge and only required when a creator asks to be paid.
5. **Earning eligibility is automatic.** When a track crosses the earning threshold, the creator is notified and invited to complete KYC.

## 2. What creators can release

| Type | Launch | Notes |
|---|---|---|
| **Single** | ✅ | One track |
| **EP** | ✅ | 3–6 tracks |
| **Album** | ✅ | 7+ tracks |
| **Playlist** | ✅ | Public, curated by the creator; does not earn royalties directly |
| **Remix / cover** | ✅ with rights attestation | Takedown if uncleared |
| **Instrumental / acapella / stems** | Later | Paid download / marketplace |
| **Music video** | Later | Reuse Studio video export |
| **Sample pack / prompt pack** | Later | Marketplace |

Do not launch with every format. Singles, EPs, albums, and public playlists cover the core creator need.

## 3. Publish flow

```
Draft
  → automated checks
      audio stored and playable
      title, cover, genre, language
      rights attestation
      explicit flag
      duplicate / banned-content checks
  → live
  → post-publication review
      reports
      spot checks
      fraud signals
  → takedown, or stay live
```

**Rules**

- Automated checks are the gate. No human pre-approval.
- A release can be taken down after publication for rights, fraud, or policy violations.
- The creator sees `Live` immediately and can share the page.
- The admin queue becomes a **moderation queue**, not an approval queue.
- New creators can be spot-checked more often, but that does not block publishing.

**Why**

- Pre-approval does not scale, adds days of latency, and makes the platform feel hostile.
- Post-publication moderation is the norm for creator platforms: publish, report, review, remove.
- Automated checks catch the cheap failures; humans handle reports and edge cases.

## 4. Badge vs payout verification

| Requirement | Badge | Payout |
|---|---|---|
| Create a page | No | No |
| Publish | No | No |
| Verified check | Yes, optional request | No |
| Identity / KYC | No | Yes, before first payout |
| Tax information | No | Yes |
| Payout account | No | Yes |

**Badge:** identity + authenticity review; trust signal; revocable; optional.

**KYC:** legal name, ID, selfie, tax ID, payout account; required only when money is requested.

Never call KYC “verification” in the UI. Call it **payout verification** so it is not confused with the badge.

## 5. Earning eligibility and notifications

### Track-level eligibility

A track becomes **earning-eligible** when:

- ≥ **500 valid streams** and ≥ **50 unique listeners** in the period (launch thresholds; revisit), or
- a lower lifetime threshold for the creator’s first release, to give new creators an early win.
- rights are attested, the creator has no active strike, and the audio is playable.

### What happens

1. Eligibility engine marks the track `earning_eligible` and records `eligible_at`.
2. Creator gets an in-app + email notification.
3. Earnings accrue from `eligible_at` into a **pending verification** balance.
4. Creator completes payout KYC.
5. Pending balance becomes **available** after the holdback and is paid in the monthly cycle.

### Notification copy

At 50% of the threshold:

> **Halfway to earning**
> *Bassac Moon* has 240 valid streams. At 500 it becomes eligible to earn. Keep sharing your page.

At 100%:

> **Bassac Moon is eligible to earn**
> Complete payout verification to unlock your earnings. It takes about 3 minutes.

After KYC:

> **Payouts are active**
> Your eligible tracks now accrue earnings. The next payout run is on the 5th.

### Why accrue from eligibility, not KYC

- It rewards the creator for the audience they built before they knew about payouts.
- It avoids a “lost earnings” feeling.
- Fraud risk is handled by the holdback, stream validation, and the KYC gate before money moves.

## 6. Playlists

- Creators can create and publish playlists immediately.
- Playlists are discovery surfaces; they do not earn royalties directly.
- A playlist can include the creator’s tracks and other creators’ tracks (with attribution).
- Editorial playlists remain staff-curated and clearly labeled.

## 7. Admin and moderation

- No release approval queue.
- A moderation queue for reports, spot checks, fraud, and appeals.
- Takedown SLA: 24 hours for triage, 72 hours for action.
- Every takedown has a reason, an audit entry, and an appeal path.
- Repeat infringers get strikes and removal.

## 8. Success metrics

- Time from “Publish” click to live: **< 10 seconds**.
- % of releases auto-published without human touch: **> 95%**.
- Time from eligibility to first notification: **< 1 hour**.
- Eligibility → KYC completion rate: **> 40%** within 14 days.
- Takedown triage within 24h: **> 95%**.

## 9. Implementation notes

- `CreatorReleaseService.submit` publishes immediately after validation; the admin `decide` path remains for manual publishing and takedowns.
- `creator_releases.status` uses `published` directly; `submitted`/`in_review` remain for legacy rows.
- Add `earning_eligible`, `eligible_at`, `eligibility_notified_at`, and `pending_verification_micros` to the track/release earnings model.
- Eligibility check runs daily (or hourly), reads `valid_streams`, writes eligibility, and enqueues notifications.
- KYC remains a separate gate in the payout service.
