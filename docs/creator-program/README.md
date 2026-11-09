# Camxora Creator Program — Documentation Set

**Status:** Proposal / business requirements. No code changes made.
**Date:** 2026-11-09
**Owner:** Product + Platform
**Surfaces:** `camxora.com` (public + creator hub), `platform_api` (domain + admin APIs), `admin_portal` (ops consoles)

---

## 1. Recommendation in one page

Launch the **Camxora Creator Program (CCP)** as a **curated, identity-first program built on the existing streaming catalog** — not as an open marketplace and not as a second social network.

The program has four pillars, in this order:

1. **Identity** — a real creator profile, handle, public page, verified badge.
2. **Publishing** — one canonical release pipeline from a generation to the public catalog.
3. **Analytics** — honest, fraud-filtered numbers a creator can act on.
4. **Earnings** — a transparent monthly **Creator Fund** plus tips/downloads, paid through a ledger that reconciles to the cent.

Everything else (collaborator splits, marketplace, subscriptions, brand briefs, DSP distribution) is deliberately deferred until the four pillars are trustworthy.

### Why this order

- The public surfaces today are **static mockups**: `/artist/[id]`, `/discover`, `/community`, `/artist-program` use hard-coded fictional artists ("Kanya", "Dara", "Malis", "Rithy"), fake play counts, and "Follow" buttons that do nothing. Shipping a program on top of that would be fake social proof.
- The catalog, play counts, likes, uploads, reports, mail, credits, KHQR/Chmaba payments, marketplace, and download purchases already exist and can be reused.
- A creator program without trustworthy earnings math is worse than no program. One disputed payout destroys trust faster than a missing feature.
- Cambodia-first economics mean **direct support (tips, downloads, services) will out-earn streaming royalties for most creators for a long time**. The royalty pool is a retention and credibility tool, not an income promise.

### Program shape

| Tier | How you enter | Public badge | Can earn |
|---|---|---|---|
| **Creator** | Free. Complete profile + publish 1 track. | None | Tips only (after KYC) |
| **Verified Creator** | Manual identity + authenticity review | Blue check | Creator Fund, tips, downloads, marketplace |
| **Partner Creator** | Invite only (editorial/business) | Partner mark | Everything + higher share, advances, distribution support |

**Critical separation:** *badge ≠ payout eligibility*. A verified badge is trust. Monetization requires **KYC + policy compliance + thresholds**. Never sell badges.

### Money model at launch

| Stream | Split | Launch |
|---|---|---|
| Creator Fund (royalty pool) | 100% to creators | ✅ Phase 3 |
| Tips / support | 90% creator / 10% platform | ✅ Phase 3 |
| Paid downloads & licenses | 70% creator / 30% platform | Phase 4 |
| Sample/prompt packs | 80% creator / 20% platform | Phase 4 |
| Services / booking leads | 90% creator / 10% lead fee | Phase 4 |
| Creator subscriptions | 85% creator / 15% platform | Later |
| Brand briefs / challenges | Prize pool + platform fee | Later |

### Non-negotiables

- No per-stream income guarantees. Publish the pool formula, caps, and weights.
- No payout without KYC and a named bank/Wing/ABA/KHQR account.
- No payout run without maker-checker approval and a reconciliation report.
- No public earnings, emails, or listener PII.
- No owner plays, bot plays, VPN farms, or self-follows count toward money.
- No launch while fictional artists remain on public pages.

---

## 2. Documents

| Doc | What it answers |
|---|---|
| [BRD.md](./BRD.md) | Why the program exists, who it serves, how it works, monetization policy, trust & safety, KPIs, risks, launch gates |
| [PRODUCT_SPEC.md](./PRODUCT_SPEC.md) | Every feature, page, state, notification, and edge case — page by page |
| [USER_FLOWS.md](./USER_FLOWS.md) | End-to-end journeys, state machines, and how the program connects to every other Camxora feature |
| [SAMPLE_CREATORS.md](./SAMPLE_CREATORS.md) | Deferred sample pack: 8 fictional creators, Khmer-first discography (3 pop albums × 10 + 7 EPs), SLai avatar plan |
| [TECHNICAL_DESIGN.md](./TECHNICAL_DESIGN.md) | Current-state audit, data model, migrations, APIs, jobs, admin RBAC, security, test matrix |
| [ROADMAP.md](./ROADMAP.md) | Phasing, dependencies on the Studio work, capacity, acceptance criteria, open decisions |

---

## 3. What already exists (and what is broken)

### Reusable today

| Capability | Where |
|---|---|
| User identity + auth | `users` (`platform_db`), `platform_api` middleware |
| Public catalog | `stream_albums`, `stream_tracks`, `/api/v3/public/streaming/*` |
| Play counts + likes | `stream_tracks.play_count`, `stream_track_likes`, `web_music_likes`, `web_music_play_counts` |
| Generation library | `suno_tasks` (`source='web_music'`), `/api/v3/web-music/generations` |
| Upload / storage pipeline | `StreamingUploadService`, B2 + signed playback |
| Reports | `web_music_reports` |
| Payments | KHQR, ChmabaPay, billing/topups |
| Credits | `credit_wallets`, `credit_transactions`, micro-credit migration 028 |
| Mail + notifications | `mail_*` tables, `notification_queue` |
| Marketplace | `marketplace_items` (migration 041) |
| Paid downloads | `download_purchases` (migration 0016 in `musicapi`) |
| Admin console | `admin_portal` (Vite/React) + `platform_api/routers/admin*` |

### Broken / missing (must fix before launch)

| Gap | Evidence | Impact |
|---|---|---|
| `valid_streams` table is queried but never created | `streaming_catalog_service.py`, `streaming_admin.py` | Play/royalty stats silently return 0 |
| `royalty_ledger` table is queried but never created | `streaming_admin.py` | Admin catalog endpoint raises |
| `RoyaltyPolicyService` imported but does not exist | `streaming_admin.py:206` | `GET /streaming/admin/catalog` 500s |
| `stream_tracks.origin` read but never added | `streaming_admin.py:240` | AI vs original weighting impossible |
| No creator identity/profile/handle | No table | Pages cannot be real |
| No follow graph | No table | "Follow" is decorative |
| No application/verification/badge tables | No tables | Program cannot operate |
| No publish-to-catalog action | web-music only does B2 backfill | Library tracks never reach the public catalog |
| No earnings/payout ledger | No tables | Cannot pay anyone |
| Static fictional artists on public pages | `artist-data.ts`, `discover`, `community` | Credibility + legal risk |

---

## 4. The 10 decisions this proposal makes

1. **One creator identity = one `users.id`.** No parallel creator account.
2. **Public URL is `/creators/[handle]`.** `/artist/[id]` becomes a 301.
3. **Public page ≠ dashboard.** "Creator Studio" (private) vs "Creator Page" (public).
4. **Publishing is explicit and reviewed.** Generations are private until a creator submits a release.
5. **Badges are earned and revocable, never purchasable.**
6. **AI disclosure is mandatory**, with a transparent (not punitive) `AI Artist / AI-assisted` label.
7. **Royalties are a funded pool with weights and caps**, not a statutory per-stream rate.
8. **Payouts are monthly, manual-first, maker-checker**, via ABA/Wing/KHQR.
9. **Streams are validated** (30s/50%, non-owner, deduped, fraud-filtered) before they can earn.
10. **Collaborator splits ship after launch**, with metadata-only credits in v1 and a single attested payee.

---

## 5. Read this first if you only have 10 minutes

1. [BRD §5 — How the program works](./BRD.md#5-how-the-program-works)
2. [BRD §7 — Monetization](./BRD.md#7-monetization)
3. [TECHNICAL_DESIGN §3 — Current-state audit](./TECHNICAL_DESIGN.md#3-current-state-audit)
4. [ROADMAP §2 — Phase plan](./ROADMAP.md#2-phase-plan)
