# Camxora Creator Program — Business Requirements Document (BRD)

**Version:** 1.0 (proposal)
**Date:** 2026-11-09
**Status:** For decision
**Related:** [README](./README.md) · [Product Spec](./PRODUCT_SPEC.md) · [Technical Design](./TECHNICAL_DESIGN.md) · [Roadmap](./ROADMAP.md)

---

## 1. Executive summary

Camxora is an AI-native music platform. Today a user can generate music, keep it in a private library, download it, and — for desktop batch tasks — have it auto-ingested into a public streaming catalog under their display name. There is no creator identity, no verification, no publishing consent, no follow graph, no analytics a creator can trust, and no way to pay a creator.

The **Camxora Creator Program** turns generators into creators and listeners into an audience. It is the retention layer for the platform: generation brings people in; creators and their audience keep them.

### The thesis

> **Camxora should be the best place in Cambodia to release AI-made music and be paid fairly for it — not the biggest catalog.**

That means:

- **Curation over volume.** A verified creator with a real page and a real audience is worth more than 10,000 anonymous uploads.
- **Trust over vanity metrics.** Every number a creator sees must survive an audit.
- **Direct income over micro-royalties.** Tips, downloads, and services will pay creators more than streaming fractions for years.
- **Transparency over hype.** Publish the pool formula, the weights, the caps, and the exclusions. Never promise per-stream income.

### What we are launching

A three-tier program (Creator → Verified Creator → Partner) with:

1. A **creator profile and public page** (`/creators/[handle]`) with handle, bio, links, genres, badges, releases, top tracks, followers, and support.
2. An **application and verification workflow** with manual review, evidence, SLAs, appeals, and revocation.
3. A **publish-to-catalog pipeline** from a generation to a reviewed, scheduled release.
4. A **creator analytics dashboard** with defined, fraud-filtered metrics.
5. A **Creator Fund** (monthly royalty pool) plus **tips** at launch of monetization, with **paid downloads**, **marketplace**, and **services leads** following.
6. **Payouts** via ABA/Wing/KHQR with KYC, thresholds, holds, statements, and maker-checker controls.
7. **Trust & safety**: reports, moderation queue, strikes, appeals, impersonation checks, stream-fraud detection.

### What we are deliberately not doing

- No NFT, crypto, or token.
- No open self-serve instant payouts.
- No per-stream statutory rate or income guarantee.
- No DMs, live streaming, or a full social feed at launch.
- No multi-creator organizations (label roster) until the single-creator model is stable.
- No paid verification, paid editorial placement, or pay-to-play charts.

---

## 2. Problem statement

### For creators

| Problem | Consequence |
|---|---|
| Generating a track is easy; releasing it is not | Great tracks die in a private library |
| No public identity | Listeners cannot follow, credit, or find them again |
| No trusted numbers | Creators cannot tell what is working |
| No income path | The platform takes credits but returns no value to the creator |
| No rights clarity | Creators fear losing ownership or being copied |
| No recognition | Effort is invisible; no badge, chart, or editorial path |

### For listeners

| Problem | Consequence |
|---|---|
| Static, fictional artist pages | Discovery feels fake; no reason to return |
| "Follow" does nothing | No relationship, no notifications, no retention |
| No creator context | No bio, credits, links, or story behind the music |
| No way to support | Listeners who love a track cannot pay the creator |

### For Camxora

| Problem | Consequence |
|---|---|
| Catalog grows without identity | Undifferentiated content, weak SEO, no brand |
| No creator lock-in | Creators can move to Suno, SoundCloud, YouTube |
| No monetization loop | Revenue is one-sided (users buy credits; creators earn nothing) |
| Reputational risk | Fake artists and untraceable uploads undermine trust |

---

## 3. Opportunity & competitive context

### What comparable platforms do

| Platform | Identity | Monetization | Lesson for Camxora |
|---|---|---|---|
| **Spotify** | Artist profile, verified badge, Spotify for Artists | Streams → royalties via distributors; Discovery Mode | Trusted analytics + editorial are the product; per-stream rates are opaque and contested |
| **SoundCloud** | Profile, follows, comments | Fan-powered royalties, Next Pro | Direct fan support works better than pro-rata for mid-tail creators |
| **Bandcamp** | Rich artist page | Direct sales, name-your-price | Creators will promote a page that pays them directly |
| **Audiomack** | Profiles, charts | Tips, paid downloads | Strong in mobile-first emerging markets |
| **Boomplay** | Profiles, charts | Ad-supported + subscriptions | Africa-first localization matters more than catalog size |
| **Suno / Udio** | Minimal public identity | None for creators | The gap: generation without a release/earnings layer |
| **YouTube** | Channel + verification | Ads, memberships, Super Thanks | A creator page with multiple income streams beats a single royalty rate |

### The Cambodian context (design constraints)

- **Payments:** KHQR is dominant; ABA and Wing are trusted; card penetration is low. Payouts must work without Stripe.
- **Currency:** USD is used daily; KHR is the local currency. Display both, settle in USD by default.
- **Mobile-first:** most listeners are on Android, often on metered data. Pages must be lightweight.
- **Language:** Khmer UI and Khmer-language creator support are required, not optional.
- **Trust:** formal contracts and visible payout proof matter. A public "paid creators this month" number is a growth asset.
- **Music market:** Don Don Donki-style covers, Khmer pop, hip-hop, EDM, and wedding/ceremony music are high-demand genres. Creator tools should support Khmer lyrics, romanization, and traditional instruments.

### Why now

- The catalog and upload pipeline already exist (`stream_albums`, `stream_tracks`, B2, signed playback).
- Likes, play counts, reports, and admin catalog tooling exist.
- The Studio work in parallel will increase generation volume; without a release/earnings layer that volume creates support load, not value.
- The half-built royalty scaffolding in `streaming_admin.py` shows the team already intended this. Finishing it properly is cheaper than starting later.

---

## 4. Personas

### P1 — Sokha, 24, first-time AI artist (Phnom Penh)

- Makes Khmer pop and ballad tracks on her phone after work.
- Has 12 generations, 3 she likes.
- Wants: a page that looks real, a verified badge, and to know if anyone listens.
- Fears: being copied, wasting time, hidden fees.
- Success: publishes 3 tracks, gets 200 valid streams, earns her first $5 tip, shares her page on TikTok.

### P2 — Vannak, 31, semi-pro producer (Siem Reap)

- Produces for local singers; uses AI for demos and backing tracks.
- Has an audience on YouTube and Facebook.
- Wants: a canonical profile, credits for collaborators, paid downloads, and a way to sell custom songs.
- Success: sells 10 downloads/month and gets 3 custom-song leads.

### P3 — Dara, 19, listener and superfan

- Discovers music on TikTok and YouTube, listens on mobile.
- Wants: follow creators, save tracks, support with a small tip.
- Success: follows 5 creators, gets notified of releases, tips $1 twice.

### P4 — Malis, ops moderator (Camxora)

- Reviews applications, releases, reports, and appeals.
- Needs: a queue with SLAs, evidence, one-click decisions, audit trail.
- Success: clears the queue daily, <1% reversal rate on appeals.

### P5 — Rithy, finance/admin (Camxora)

- Runs the monthly payout cycle.
- Needs: a locked ledger, reconciliation report, maker-checker approval, statements.
- Success: pays 100% of creators on time with zero reconciliation breaks.

### P6 — Kanya, Partner creator / label (Phnom Penh)

- Manages 6 artists and a release calendar.
- Needs: roster view, higher share, editorial access, distribution support.
- Success: moves her roster to Camxora exclusively.

---

## 5. How the program works

### 5.1 Program tiers

| Tier | Entry criteria | Badge | Benefits | Earnings |
|---|---|---|---|---|
| **Creator** | Account in good standing; complete profile; 1 published track | None | Public page, analytics, follows, publish, challenges | Tips after KYC |
| **Verified Creator** | ≥30 days old; ≥3 published tracks or ≥1 release with 500 valid streams; complete profile; identity + authenticity review; no active strike | Blue check | All Creator benefits + Creator Fund eligibility + downloads + marketplace + priority review | All streams |
| **Partner Creator** | Invite only: editorial fit, audience, business alignment, signed agreement | Partner mark | All Verified benefits + higher revenue share, advances, editorial calendar, distribution/DSP support, roster view (pilot) | All streams + negotiated terms |

**Rules**

- A creator can be **Creator** forever without applying for verification.
- Verification is **free**, reviewed manually, and can be revoked.
- Partner status is contractual and time-bound (12 months, renewable).
- Tier is shown on the public page; earnings are never public.

### 5.2 Application flow

```
Eligible account
   │
   ▼
Application form (identity, links, genres, goals, rights attestation)
   │
   ▼
Automated checks (account age, strikes, duplicate identity, banned names, link reachability)
   │
   ▼
Manual review (2 reviewers for Partner; 1 for Verified)
   │
   ├── Approved ──► Badge granted + onboarding checklist + payout setup prompt
   ├── Changes requested ──► Creator edits and resubmits (no penalty)
   └── Rejected ──► Reason + appeal window (14 days)
```

**SLA:** first response within 3 business days; decision within 7 business days. Partner: 10 business days.

**Evidence required**

- **Identity:** legal name, date of birth, country, government ID (front/back) or business registration for labels. Stored encrypted; access logged.
- **Authenticity:** at least 3 tracks or 1 release with meaningful traction; links to at least one external presence (YouTube, TikTok, Facebook, Instagram) that matches the creator identity.
- **Rights:** attestation that the creator owns or has cleared all samples, vocals, lyrics, and artwork; voice-cloning consent if applicable.
- **Notability (soft signal, not a hard gate):** 500 valid streams, 50 unique listeners, 500 followers, or 5k external followers. Used to prioritize review, not to reject promising new creators.

### 5.3 Verification badges

| Badge | Meaning | Granted by | Expires |
|---|---|---|---|
| **Verified Creator** | Identity confirmed; authentic original creator | Manual review | 12 months; re-review |
| **Founding Creator** | Joined in the 2026 launch cohort | Automatic, capped | Permanent (historical) |
| **Top Creator** | Top 1% by valid streams in a month | Automatic | 1 month |
| **Partner** | Contractual partner | Business | Contract term |
| **Label / Studio** | Verified organization | Manual + registration | 12 months |
| **AI Artist** | Primarily AI-generated persona | Self-declared + reviewed | While active |
| **AI-assisted** | Human-led with AI tools | Self-declared | While active |
| **Explicit** | Explicit content flag | Auto + review | While content is live |
| **Staff / Editorial** | Camxora team | Internal | Employment |

**Badge rules**

- Badges are never sold, bundled with credits, or given for spend.
- One identity badge per account; content badges can stack.
- Badges are removed for: impersonation, fraud, 3 strikes, 12 months inactive, request.
- Removal is appealable within 14 days.
- Public tooltip explains what each badge does and does not mean.

### 5.4 Handle & identity rules

- Handle: 3–30 chars, `a-z0-9_`, must start with a letter, case-insensitive unique.
- Reserved: `admin`, `camxora`, `support`, `official`, `staff`, `verified`, `music`, `api`, and public-figure names.
- Change limit: once per 90 days; old handle redirects for 12 months.
- Display name: 1–50 chars; no impersonation, no "official" unless authorized, no misleading claims.
- One creator page per user at launch. Organizations get a `Label` account type in Phase 4.

### 5.5 Creator lifecycle states

```
applied → in_review → verified → active → at_risk → suspended → offboarded
                └── changes_requested ──┘
```

| State | What happens |
|---|---|
| `applied` | Application received; limited profile editing |
| `in_review` | Badge pending; can publish but not earn |
| `verified` | Badge live; can complete KYC and earn |
| `active` | Normal operation |
| `at_risk` | 1 strike or fraud flag; earnings held; can appeal |
| `suspended` | 2 strikes or serious violation; page hidden; payouts frozen |
| `offboarded` | Removed from program; catalog may remain if rights are clear; final settlement |

### 5.6 Offboarding & deletion

- Creator can leave the program at any time; page unpublishes within 24h.
- Outstanding earnings are paid at the next cycle if KYC is complete and no dispute.
- Account deletion: page removed, catalog tracks unpublished or anonymized, financial records retained per law, KYC docs deleted after the retention period.
- Platform can remove a creator for fraud, repeated infringement, or legal requirement, with written reason and appeal path (except illegal content, which is immediate).

---

## 6. Creator identity & public page (business requirements)

### 6.1 Profile vs page vs dashboard

| Surface | Audience | Purpose |
|---|---|---|
| **Account profile** (`/account`) | Private | Email, password, security, preferences |
| **Creator Studio** (`/creator/*`) | Private | Releases, analytics, earnings, payouts, profile editing |
| **Creator Page** (`/creators/[handle]`) | Public | Identity, music, follows, support, booking |

### 6.2 Public page requirements

**Above the fold**

- Avatar, display name, verified/partner badge, handle.
- Tagline (120 chars) and genres.
- Monthly listeners (last 28 days), total valid streams, followers.
- Primary actions: **Play**, **Follow**, **Support**.
- Cover/banner image with safe-area cropping.

**Modules**

1. **Top tracks** — top 5 by valid streams in the last 28 days; play inline.
2. **Releases** — albums/singles, newest first, with release date and track count.
3. **Playlists** — public playlists featuring the creator.
4. **About** — bio (2,000 chars), location, active since, influences, links (max 5).
5. **Credits** — collaborators on releases (Phase 4).
6. **Support** — tip jar, paid downloads, booking link (if enabled).
7. **Similar creators** — 4 recommendations, genre + listener overlap.
8. **Report** — report profile or content.

**SEO & sharing**

- Server-rendered, indexable, canonical URL.
- OpenGraph/Twitter cards with dynamic OG image.
- `MusicGroup`/`Person` + `MusicAlbum`/`MusicRecording` JSON-LD.
- Sitemap includes every active creator and release.
- Khmer and English metadata; `hreflang` for `km` and `en`.

**Performance**

- LCP < 2.0s on 4G mid-range Android; page JS < 150KB gzipped; images responsive AVIF/WebP.
- Playback starts < 1.5s with signed URL prefetch.

**Privacy**

- Never show email, legal name, payout details, exact earnings, or listener identities.
- Follower list private by default; count public.
- Analytics hidden below 100 unique listeners to prevent de-anonymization.

### 6.3 Follows

- Follow/unfollow with optimistic UI; idempotent API.
- Follower count updates within 60s; no fake inflation.
- New-release notification to followers (batched, opt-out).
- Block/mute supported; blocked users cannot follow or comment.
- Self-follow and bot-follow are rejected and flagged.

### 6.4 Creator directory

- `/creators` with search, genre filter, country, verified-only, sort by monthly listeners / newest / trending.
- Featured shelf curated editorially; clearly labeled "Editorial".
- No pay-to-rank.
- Pagination + SSR for SEO.

---

## 7. Monetization

> **Principle:** pay creators from money the platform actually has, on a schedule it can defend, with math it can explain.

### 7.1 Revenue streams and priority

| # | Stream | Creator share | Platform share | Phase | Why |
|---|---|---|---|---|---|
| 1 | **Creator Fund** (royalty pool) | 100% of pool | 0% (funded from revenue) | 3 | Retention, credibility, aligns with listening |
| 2 | **Tips / support** | 90% | 10% | 3 | Highest conversion in emerging markets |
| 3 | **Paid downloads** | 70% | 30% | 4 | Existing `download_purchases`; clear value |
| 4 | **Commercial licenses** | 70% | 30% | 4 | Sync/brand use; higher ticket |
| 5 | **Sample/prompt packs** | 80% | 20% | 4 | Existing marketplace; creators as sellers |
| 6 | **Services leads** | 90% | 10% | 4 | Custom songs, mixing, jingles |
| 7 | **Creator subscriptions** | 85% | 15% | Later | Recurring billing complexity |
| 8 | **Brand briefs / challenges** | Prize pool | Fee | Later | Brand-funded, not platform-funded |

**Ordering rationale:** The Fund and tips prove the promise ("Camxora pays creators"). Downloads and marketplace create real income. Subscriptions and brand deals require billing and sales maturity we do not have yet.

### 7.2 Creator Fund (royalty pool)

#### Funding formula

```
Pool_month = clamp(
    max(FLOOR_USD, REVENUE_SHARE_PCT × NetListeningRevenue_month),
    FLOOR_USD,
    CAP_PCT_GROSS × GrossPlatformRevenue_month
)
```

Recommended launch values (finance approval required):

| Parameter | Launch | Notes |
|---|---|---|
| `FLOOR_USD` | $3,000/month | Guarantees a real payout while listening revenue is small |
| `REVENUE_SHARE_PCT` | 15% | Of net listening-attributed revenue (subscriptions, listener credits, ads later) |
| `CAP_PCT_GROSS` | 25% | Protects unit economics |
| `RESERVE_PCT` | 10% | Held 90 days for fraud/refunds |
| `HOLDBACK_DAYS` | 90 (new creators) / 30 (standard) | Absorbs chargebacks |
| `MIN_PAYOUT_USD` | $20 | Below this, balance rolls over |

> The Fund is **not** a fixed per-stream rate. The rate is an output: `Pool ÷ total weighted streams`. It changes monthly. Publish the result.

#### Eligibility

- Verified Creator, KYC complete, no active strike.
- ≥ **500 valid streams** and ≥ **50 unique listeners** in the period (launch threshold; revisit after 3 months).
- Account ≥ 30 days old.
- At least 1 published release in the period.

#### Weighted streams

Not all streams are equal. Weight by origin:

| Origin | Weight | Definition |
|---|---|---|
| `original` | 1.0 | Human-written/performed; AI used only as a tool; cleared samples/vocals |
| `ai_assisted` | 0.6 | Human-led composition/lyrics/vocals with significant AI generation |
| `ai_generated` | 0.3 | Primarily prompt-generated; no human performance |

Weight is stored on the release (`stream_tracks.origin`) and attested by the creator; misrepresentation is a strike.

#### Caps

- Per track: **500,000 weighted streams/month** (prevents one viral loop from draining the pool).
- Per creator: **40% of the pool/month at launch**, tightening to **20% at scale**. Early programs have few creators, so a tight cap would punish the only people generating real listening; the cap exists to stop one account taking almost everything, not to suppress success.
- Excess is not paid; it is redistributed to uncapped creators in a second pass (documented, not silently kept).
- Cap values are policy-configurable, versioned, and published.

#### Worked example

Assume Pool = $3,000; total weighted streams = 2,000,000 → rate = **$0.0015 per weighted stream**. Amounts below are **gross accruals before caps, reserve, and holdback**.

| Creator | Origin | Raw valid streams | Weight | Weighted | Accrual |
|---|---|---|---|---|---|
| A | original | 400,000 | 1.0 | 400,000 | $600.00 |
| B | ai_assisted | 800,000 | 0.6 | 480,000 | $720.00 |
| C | ai_generated | 2,000,000 | 0.3 | 600,000 | $900.00 |
| D | original | 300,000 | 1.0 | 300,000 | $450.00 |
| E | original | 220,000 | 1.0 | 220,000 | $330.00 |
| **Total** | | | | **2,000,000** | **$3,000.00** |

> **Cap in practice:** C has 600,000 weighted streams, above the per-track cap of 500,000. C is paid on 500,000 weighted ($750) before redistribution; the remaining $150 is redistributed pro-rata to uncapped creators in a second pass. The per-creator cap (40% = $1,200) does not bind here. The final ledger is deterministic — see [Technical Design §7.3](./TECHNICAL_DESIGN.md#73-royalty-calculation). Engineering must test the cap, redistribution, and rounding paths precisely.

#### Period close

1. `T+0` (1st, 02:00 ICT): freeze raw events for the previous calendar month.
2. `T+1`: dedupe, fraud pass, compute `valid_streams` and weights.
3. `T+2`: compute pool, rate, caps; generate preliminary ledger.
4. `T+3`: finance reviews reconciliation; policy simulation report.
5. `T+4`: ledger locked; creator statements published; payout run created.
6. `T+5`: maker-checker approval; payouts sent; statuses updated.

Any correction after lock is a **new adjustment entry**, never an edit.

### 7.3 Tips / support

- Creator enables a tip jar with suggested amounts ($1, $3, $5, $10, custom).
- Payment methods: KHQR (primary), ChmabaPay, card where available.
- 90/10 split; platform fee shown before payment.
- Minimum $1; maximum $500 per transaction; rate-limited.
- Tips are non-refundable except fraud/duplicate; disputes handled by support.
- Public "supporter count" optional; amounts private by default.
- Payout via the same monthly cycle.

### 7.4 Paid downloads & licenses

- Fixed price tiers: **$1.99 (MP3), $4.99 (WAV + stems), $9.99 (commercial license)**. Creator can opt out; Partner can set custom prices.
- 70/30 split.
- License terms displayed at checkout (personal vs commercial; streaming vs sync; attribution).
- Existing `download_purchases` extended with `creator_id`, `license_type`, `price`, `platform_fee`, `creator_net`.
- Refund policy: 14 days if file not downloaded; fraud always refundable.
- Watermark previews for unpaid downloads.

### 7.5 Marketplace (sample/prompt packs)

- Creators sell packs (loops, vocals, presets, prompt recipes, project files).
- 80/20 split; instant download after payment.
- Content review for copyright and malware.
- Ratings/reviews after purchase; abuse moderation.
- Existing `marketplace_items` extended with `seller_id`, `file_key`, `license`, `platform_fee`.

### 7.6 Services / booking leads

- Creator lists services: custom song, jingle, mixing, vocal feature, event performance.
- Listener submits a brief; platform routes the lead; creator quotes and delivers off-platform.
- Platform charges a **10% lead fee** on the first transaction or a flat $2–$5 per qualified lead (test both).
- Dispute handling and no-show policy.
- This is low-engineering and high-value in Cambodia; ship early.

### 7.7 Creator subscriptions (later)

- Monthly supporter tier with exclusive tracks, early access, Discord/Telegram role.
- 85/15 split.
- Requires recurring billing (KHQR recurring is unreliable), dunning, and churn handling. Do not launch before the one-time flows are stable.

### 7.8 Brand briefs & challenges

- Brands fund a brief (e.g., "30-second Khmer pop jingle for a telecom").
- Platform takes a 15–20% facilitation fee; the rest is prize money.
- Clear judging rubric, deadline, and rights assignment.
- Existing `/community` weekly challenge becomes the consumer-facing version (credits prizes at launch).

### 7.9 What creators must never be told

- "You will earn $X per stream."
- "Guaranteed income."
- "Top creators earn $Y" without a real, audited cohort and a date range.
- "Verification guarantees quality."

Every public claim must link to the **Royalty Policy** and the current month's published rate.

---

## 8. Payouts, KYC, and tax

### 8.1 Payout rails (Cambodia-first)

| Rail | Use | Notes |
|---|---|---|
| **ABA Bank** | Default bank transfer | Account name must match KYC |
| **Wing** | Wallet transfer | Popular with younger creators |
| **KHQR** | Fallback / small amounts | Good for <$50 |
| **Bakong** | Future | Requires API integration |
| **PayPal / Wise** | Diaspora creators | Phase 4, fee passed to creator |

### 8.2 Payout rules

- Cycle: monthly, on the **5th** (ICT), for the prior month.
- Minimum: **$20**; below threshold rolls over.
- New creators: 90-day hold on first earnings; standard 30-day hold afterward.
- Reserve: 10% of Fund held 90 days.
- Fees: platform covers the first $1 per transfer; excess deducted from the payout.
- Currency: USD; KHR equivalent shown at the day's rate.
- Statement: PDF + CSV with line items (royalty, tip, download, marketplace, adjustment).
- Failure handling: retry once, then hold and notify; wrong account details are the creator's responsibility after verification.
- Negative balance (chargeback/clawback) offsets future earnings; no cash collection.

### 8.3 KYC

Required before the **first payout** or at **$100 lifetime earnings**, whichever comes first.

| Field | Required |
|---|---|
| Legal name | ✅ |
| Date of birth (18+) | ✅ |
| Country / address | ✅ |
| Government ID (front/back) | ✅ |
| Selfie / liveness | ✅ |
| Tax ID (TIN) or declaration | ✅ |
| Bank/Wing account in legal name | ✅ |
| Business registration (labels) | ✅ |

- Minors: not eligible for monetization; guardian consent does not override platform policy.
- Documents encrypted at rest; decryption access logged; retained only as long as legally required.
- Sanctions/PEP screening: manual checklist at launch; vendor later.

### 8.4 Tax

- Camxora withholds tax where required by Cambodian law; otherwise the creator is responsible.
- Annual earnings statement issued to every creator who earned ≥$250.
- VAT treatment of digital services and withholding rates **must be confirmed by Cambodian tax counsel** before the first payout.
- Keep a per-payout audit trail: gross, fee, withholding, net, rail reference.

> **Status:** Tax and withholding are unresolved legal questions. Do not launch payouts until finance/counsel signs off on the withholding matrix and invoice/statement templates.

---

## 9. Analytics & metric definitions

### 9.1 Definitions (must be identical in UI, API, and payout)

| Metric | Definition | Notes |
|---|---|---|
| **Play** | Playback start with ≥5 seconds of audio | Near-real-time |
| **Valid stream** | ≥30s or ≥50% of duration, non-owner, deduped, not fraud-flagged | Basis for charts and royalties |
| **Royalty stream** | Valid stream that passes eligibility, weights, and caps | Basis for payment |
| **Unique listener** | Distinct authenticated user in the period | Anonymous listeners counted separately, never paid |
| **Monthly listeners** | Unique listeners in the last 28 days | Public number |
| **Save** | Like or add-to-playlist (distinct per user/track/day) | Not double-counted |
| **Follower** | Active follow relationship | Public count |
| **Completion rate** | Valid streams ÷ plays | Quality signal |
| **Skip rate** | Plays <30s ÷ plays | Quality signal |
| **Avg. listen time** | Total seconds ÷ plays | Quality signal |
| **Traffic source** | First-touch: discover, search, profile, playlist, chart, external, direct | Privacy-safe |
| **RPM** | Net earnings per 1,000 valid streams | Creator-facing |
| **Payout accuracy** | Paid ÷ ledger expected, to the cent | Ops KPI |

### 9.2 Anti-fraud rules for counting

- One valid stream per **listener × track × 6 hours**; max **20 royalty streams per listener per day**.
- Owner plays never count (desktop, web, API).
- Exclude: datacenter/VPN/proxy ASNs, known bot user agents, emulators, headless browsers, impossible travel.
- Exclude plays with <30s and no completion.
- Flag listener concentration: if the top 1% of listeners drive >30% of a creator's streams, hold the creator for review.
- Flag velocity: >10× the creator's 30-day median in 24h.
- Flag device graphs: >5 accounts per device, >3 accounts per IP paying each other.
- Quarantine: 48 hours before a stream is "final"; 30-day hold before money is available.
- Corrections are adjustment entries, never silent edits.

### 9.3 Creator dashboard requirements

- Date range: 7/28/90 days, 12 months, custom.
- Dimensions: track, release, genre, country, source, device.
- Comparisons: previous period, same period last year (when data exists).
- Export: CSV; Partner API later.
- Freshness label: "Updated hourly · Final after 48h".
- Empty states explain what to do next, not just "no data".
- Thresholds: hide country/device breakdowns below 100 unique listeners.

### 9.4 Public numbers

- Monthly listeners, followers, total valid streams, top tracks.
- Never show earnings, revenue, skip rate, or listener identity.
- Round large numbers (1.2K, 2.4M) and state the period.

---

## 10. Content, publishing, and rights

### 10.1 Publishing pipeline

```
Draft → Submitted → Auto-checks → In review → Changes requested → Approved → Scheduled → Published → Taken down
```

**Required metadata:** title, cover art (≥1400×1400), primary genre, language, explicit flag, lyrics (optional but recommended), credits, release date, rights attestation, AI disclosure, distribution scope.

**Auto-checks:** file integrity, duration, cover dimensions/safety, duplicate audio fingerprint (Phase 4), banned words, metadata completeness, account standing.

**Review SLA:** 3 business days. Partner: 1 business day.

**Scheduling:** creators can set a future release date; published at 00:00 ICT; pre-save/follow notification.

### 10.2 Rights model

- Creator grants Camxora a **non-exclusive, worldwide license** to host, stream, promote, and sublicense playback on Camxora properties for as long as the release is published.
- Creator retains ownership.
- Creator can request takedown at any time; Camxora removes within 72h (except legal holds).
- Camxora may use excerpts for promotion (≤30s) with credit.
- Exclusive windows and DSP distribution are separate Partner agreements.
- AI training on creator content: **opt-in only**, separate consent, never buried in ToS.

### 10.3 AI disclosure

| Label | When | Public display |
|---|---|---|
| `original` | Human composition/performance; AI as tool | No AI label |
| `ai_assisted` | Human-led, significant AI generation | "AI-assisted" chip in About |
| `ai_generated` | Primarily prompt-generated | "AI artist" chip in About |

- Misrepresentation is a strike and can trigger clawback.
- Voice cloning requires verified consent from the person whose voice is used (reuse existing voice verification endpoints).
- AI personas must disclose that they are fictional; no impersonation of real artists.

### 10.4 Content policy (summary)

Prohibited: hate, harassment, sexual content involving minors, non-consensual sexual content, graphic violence, illegal activity, impersonation, unauthorized voice cloning, copyright infringement, malware, spam, misleading metadata, and manipulation of charts/streams.

Enforcement ladder:

1. **Warning** + required fix.
2. **30-day monetization suspension** + content review.
3. **Removal from program** + catalog unpublish.
4. **Immediate ban** for illegal content, CSAM, or severe fraud.

Every action is logged, reasoned, and appealable (except illegal content).

### 10.5 Takedowns & disputes

- Report intake: web form + in-app + email.
- Triage within 24h; action within 72h.
- Repeat-infringer policy: 3 valid copyright strikes = removal.
- Counter-notice process with 10-day window.
- Financial impact: earnings from infringing content are frozen and may be clawed back.

---

## 11. Trust & safety

### 11.1 Risk register (operational)

| Risk | Signal | Response |
|---|---|---|
| Stream farming | Velocity, listener concentration, device graphs | Quarantine, hold, clawback, strike |
| Fake followers | Follower velocity, low engagement | Remove followers, warning, strike |
| Impersonation | Name/handle/image similarity | Reject verification, takedown, ban |
| Voice cloning without consent | Report or detection | Immediate takedown, legal escalation |
| Copyright infringement | Report or fingerprint | Takedown, strike, freeze earnings |
| Chart manipulation | Coordinated playlists/accounts | Disqualify, reset counts, strike |
| Payout fraud | Mismatched KYC/bank, multiple accounts | Hold, manual review, ban |
| Account takeover | Login anomalies | Step-up auth, freeze payouts, support |
| Tax/KYC evasion | Inconsistent identity | Block payout, report if required |

### 11.2 Moderation operations

- Queues: applications, releases, reports, appeals, fraud, payouts.
- SLAs: applications 3d, releases 3d, reports 24h triage, appeals 14d.
- Two-reviewer rule for Partner and for any ban >30 days.
- Moderation UI shows evidence, history, related accounts, and a decision template.
- Every action writes an immutable audit record (actor, time, reason, before/after).
- Weekly calibration meeting; monthly policy review.

### 11.3 Appeals

- One appeal per decision; 14-day window.
- Different reviewer from the original decision.
- Outcome + reason communicated in-app and by email.
- Financial decisions (clawback >$50) require finance sign-off.

---

## 12. Legal & compliance

### 12.1 Documents required before launch

| Document | Purpose | Owner |
|---|---|---|
| **Creator Program Agreement** | Contractual terms, license grant, tier rules, termination | Legal |
| **Royalty Policy** | Pool formula, weights, caps, eligibility, exclusions, corrections | Product + Finance + Legal |
| **Content Guidelines** | Prohibited content, enforcement ladder, appeals | Trust & Safety |
| **Payout & Tax Policy** | KYC, thresholds, rails, withholding, statements | Finance + Legal |
| **Privacy Notice (Creator Addendum)** | Analytics, KYC data, retention, rights | Legal |
| **Copyright / Takedown Policy** | Notice-and-counter-notice, repeat infringer | Legal |
| **API Terms (Partner)** | Rate limits, data use, SLA | Legal + Platform |
| **Khmer translations** | Legally valid Khmer versions | Legal |

### 12.2 Compliance checklist

- [ ] Cambodian tax counsel sign-off on withholding/VAT.
- [ ] Business registration for payouts (entity, bank account).
- [ ] KYC/AML policy and record retention.
- [ ] Data protection: consent, access, deletion, breach response.
- [ ] Age gate for monetization (18+).
- [ ] Sanctions screening process.
- [ ] Copyright agent and takedown workflow.
- [ ] Consumer protection: clear pricing, refund policy, no misleading income claims.
- [ ] Accessibility: WCAG 2.2 AA for creator pages and dashboards.

---

## 13. Community & growth

### 13.1 Launch community features (low cost, high signal)

- **Weekly challenge** with credits prizes (existing concept, make it real): brief, deadline, entries, judging rubric, winners featured.
- **Creator spotlights** — editorial page + social posts.
- **Feedback threads** — structured, moderated, no drive-by negativity.
- **Collaboration board** — "looking for a vocalist / lyricist / producer" posts (Phase 4).

### 13.2 Growth loops

1. Creator shares public page → listener follows → release notification → repeat listen.
2. Creator shares payout proof (with permission) → new creators apply.
3. Verified badge aspirational loop: Creator → Verified.
4. Challenge entries → shareable tracks → discovery.
5. Referral: invite a creator; both get credits when the invitee publishes a first track (credits only, no cash, to limit abuse).

### 13.3 Editorial principles

- Editorial is human-curated, clearly labeled, and never sold.
- Charts are based on valid streams with published methodology and fraud exclusions.
- New creators get a **cold-start boost** (e.g., 14 days of discovery rotation) to avoid rich-get-richer dynamics.
- Genre and language diversity targets are reviewed quarterly.

---

## 14. Admin & operations requirements

### 14.1 Roles

| Role | Can do | Cannot do |
|---|---|---|
| **Support** | View creator, reset profile, resend emails, add notes | Approve payouts, view KYC docs, ban |
| **Moderator** | Review releases/reports/appeals, issue strikes | Approve payouts, edit policy |
| **Finance** | View ledger, create payout run, mark paid, export statements | Ban creators, edit content |
| **Admin** | Everything, including policy changes | Cannot both approve and pay a payout run (maker-checker) |

### 14.2 Consoles

1. **Creator CRM** — search, filters (tier, status, country, earnings, strikes), timeline, notes.
2. **Applications** — queue, evidence viewer, SLA timer, decision, bulk actions.
3. **Verification** — identity docs (encrypted), evidence, approve/reject, expiry.
4. **Releases** — pending queue, metadata diff, audio preview, approve/changes/reject.
5. **Moderation** — reports, auto-flags, appeals, strike history.
6. **Royalty** — policy editor with versioning, simulation ("what would last month pay?"), period close, lock, recalc, export.
7. **Payouts** — run preview, maker-checker, mark paid with reference, retry, reconcile, statements.
8. **Fraud** — anomaly list, listener concentration, device/IP clusters, quarantine, clawback.
9. **Settings** — thresholds, caps, weights, fees, rails, email templates.

### 14.3 Operational cadence

| Cadence | Task | Owner |
|---|---|---|
| Daily | Clear application/release/report queues | Ops |
| Daily | Review fraud alerts | Trust & Safety |
| Weekly | Creator digest, challenge results, editorial meeting | Community |
| Monthly | Close royalty period, run payouts, publish rate | Finance |
| Quarterly | Policy review, calibration, diversity review | Product + Legal |

---

## 15. KPIs & launch gates

### 15.1 North-star metric

**Monthly Earning Creators (MEC)** — creators with ≥$1 in available earnings in a month. It combines publishing, audience, and monetization into one number.

### 15.2 Launch KPIs (first 90 days)

| KPI | Target |
|---|---|
| Verified creators | 30 |
| Creators with a complete public page | 50 |
| Published releases | 150 |
| Monthly valid streams | 50,000 |
| Creators earning ≥$20/month | 10 |
| Payout accuracy | 100% to the cent |
| Median time-to-verify | ≤ 5 business days |
| Median time-to-publish | ≤ 2 business days |
| Report triage within 24h | ≥ 95% |
| Creator NPS | ≥ 40 |
| Listener follow conversion (profile view → follow) | ≥ 8% |

### 15.3 Guardrails

- Fraud rate < 1% of valid streams.
- Payout disputes < 2 per cycle.
- Support tickets per creator < 0.5/month.
- Page p95 < 1.5s; analytics p95 < 800ms.
- Zero public leakage of earnings, email, KYC, or listener PII.

### 15.4 Launch gates (all must pass)

- [ ] `valid_streams` + `royalty_ledger` + `royalty_policies` migrations applied and tested.
- [ ] `RoyaltyPolicyService` implemented; admin catalog endpoint returns 200.
- [ ] Two consecutive sandbox payout cycles reconcile to $0.00 difference.
- [ ] Legal: Creator Agreement, Royalty Policy, Payout Policy signed off.
- [ ] Tax withholding matrix approved by counsel.
- [ ] KYC and payout-account flows tested end-to-end.
- [ ] Moderation runbook + escalation contacts live.
- [ ] Khmer copy reviewed by a native speaker.
- [ ] Static fictional artists removed or clearly labeled demo.
- [ ] Mobile performance and accessibility audits passed.
- [ ] Rollback plan for payout and policy changes.

---

## 16. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Fund too small → creators disappointed | High | High | Be transparent; lead with tips/downloads; publish rate; set expectations before applying |
| Stream fraud | High | High | Validation rules, quarantine, caps, fraud console, clawback |
| Rights disputes / AI copyright ambiguity | High | High | Attestation, license grant, takedown process, counsel review |
| Payout errors | Medium | Very high | Ledger, maker-checker, reconciliation, sandbox cycles, insurance reserve |
| Tax non-compliance | Medium | Very high | Counsel sign-off, withholding, statements, records |
| Moderation capacity | Medium | Medium | SLAs, templates, prioritization, community reporting |
| Low-quality catalog flood | Medium | Medium | Curation, verification, release review, caps |
| Fake artists / impersonation | Medium | High | Verification, reserved names, similarity checks, reports |
| Creator concentration | Medium | Medium | Per-creator cap, cold-start boost, editorial diversity |
| Studio parallel work conflicts | Medium | Medium | Interface contract; creator program owns release/profile APIs; Studio calls them |
| Scope creep | High | Medium | MoSCoW, phased gates, explicit non-goals |
| Currency/FX | Low | Medium | USD settlement, KHR display, fee policy |
| Data breach (KYC) | Low | Very high | Encryption, least privilege, audit, retention, incident plan |

---

## 17. Non-goals (v1)

- NFTs, tokens, crypto payments.
- Instant/self-serve payouts.
- Advertising revenue share.
- Per-stream statutory rates or income guarantees.
- DMs, live streaming, or a full social feed.
- Multi-artist label rosters (pilot only).
- AI training on creator content by default.
- Selling verification, charts, or editorial.

---

## 18. Open decisions (need answers before Phase 1)

| # | Decision | Recommendation | Default if no answer |
|---|---|---|---|
| 1 | Program name | **Camxora Creator Program**; keep `/artist-program` as redirect | Use Creator Program |
| 2 | Launch model | Closed beta (50 creators) then open applications | Closed beta |
| 3 | Fund budget | $3,000/month floor for 6 months | $3,000 |
| 4 | Pay AI-generated tracks? | Yes, at 0.3 weight, with caps | Yes |
| 5 | Tips at launch? | Yes, Phase 3 | Yes |
| 6 | Paid downloads at launch? | Phase 4 | Phase 4 |
| 7 | KYC vendor vs manual | Manual at launch, vendor at 500 creators | Manual |
| 8 | Payout entity | Camxora's registered Cambodian entity | Confirm with finance |
| 9 | Verification bar | 3 tracks or 500 valid streams + external presence | Use recommendation |
| 10 | Collaborator splits | Metadata-only in v1; splits in Phase 4 | Metadata-only |

---

## 19. Glossary

- **Creator** — a user with a public creator profile.
- **Release** — a published album or single in the catalog.
- **Valid stream** — a qualified, non-fraudulent listen (see §9).
- **Weighted stream** — valid stream × origin weight.
- **Pool** — the monthly Creator Fund.
- **Rate** — Pool ÷ total weighted streams.
- **Cap** — maximum weighted streams a track/creator can be paid for.
- **Holdback** — days before earnings become available.
- **Reserve** — portion of the pool held for disputes.
- **Maker-checker** — one person creates a payout run, another approves it.
- **KYC** — know-your-customer identity verification.
- **MEC** — Monthly Earning Creators (north star).
