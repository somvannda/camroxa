# Camxora Creator Program — Product Specification

**Version:** 1.0 (proposal)
**Date:** 2026-11-09
**Related:** [README](./README.md) · [BRD](./BRD.md) · [Technical Design](./TECHNICAL_DESIGN.md) · [Roadmap](./ROADMAP.md)

---

## 1. Purpose and scope

This document is the page-by-page, feature-by-feature specification for the Camxora Creator Program. It defines what to build, what each screen contains, what states exist, and what "done" means.

**Surfaces**

| Surface | App | Audience |
|---|---|---|
| Public web | `camxora.com` | Listeners, prospective creators |
| Creator Studio | `camxora.com/creator/*` | Signed-in creators |
| Admin console | `admin_portal` | Camxora staff |
| API | `platform_api` (`/api/v3/*`) | All clients |

**Dependencies**

- The Studio work (parallel agent) owns generation/editing. This program owns **identity, publishing, analytics, earnings, and payouts**.
- Interface contract: Studio calls `POST /api/v3/creator/releases` with a `task_id` + `variant`; it never writes creator/catalog tables directly.

---

## 2. Scope matrix (MoSCoW)

### Must — launch

| # | Feature | Surface |
|---|---|---|
| M1 | Creator profile (handle, display name, bio, avatar, banner, links, genres, AI disclosure) | Creator Studio |
| M2 | Public creator page `/creators/[handle]` | Public |
| M3 | Creator directory `/creators` with search/filter | Public |
| M4 | Program landing `/creator-program` (replaces `/artist-program`) | Public |
| M5 | Application + status tracking | Public + Studio |
| M6 | Manual verification + badge grant/revoke | Admin |
| M7 | Publish release from a web-music generation | Studio |
| M8 | Release review queue + approve/changes/reject | Admin |
| M9 | Follow / unfollow + follower counts | Public |
| M10 | Creator analytics (plays, valid streams, listeners, saves, followers) | Studio |
| M11 | Reports + moderation queue + strikes + appeals | Public + Admin |
| M12 | Creator Fund calculation + earnings ledger | Platform |
| M13 | KYC + payout account + monthly payout run (manual) | Studio + Admin |
| M14 | Statements (PDF/CSV) | Studio |
| M15 | Notifications + lifecycle emails | Studio |
| M16 | Legal pages + Khmer localization | Public |

### Should — 90 days

| # | Feature | Surface |
|---|---|---|
| S1 | Tips / support | Public + Studio |
| S2 | Weekly challenges with credits prizes | Public + Admin |
| S3 | Creator charts (genre/period) | Public |
| S4 | CSV analytics export | Studio |
| S5 | Fraud console | Admin |
| S6 | Creator CRM timeline + notes | Admin |
| S7 | Cold-start discovery boost | Platform |
| S8 | Dynamic OG images for creator pages | Public |

### Could — later

| # | Feature |
|---|---|
| C1 | Collaborator credits + split payouts |
| C2 | Paid downloads + commercial licenses |
| C3 | Sample/prompt pack marketplace |
| C4 | Services / booking leads |
| C5 | Creator subscriptions |
| C6 | Brand briefs |
| C7 | Embeddable player |
| C8 | Partner API / label roster |
| C9 | DSP distribution |

### Won't — v1

- NFTs, crypto, tokens.
- Instant self-serve payouts.
- DMs, live streaming, full social feed.
- Paid verification or pay-to-play charts.
- Per-stream income guarantees.
- AI training on creator content by default.

---

## 3. Route map

### 3.1 Public

| Route | Purpose | Notes |
|---|---|---|
| `/creator-program` | Program landing | Replaces `/artist-program`; 301 old URL |
| `/creator-program/apply` | Application form | Auth required |
| `/creator-program/rules` | Royalty + content policy | Linked from every earnings screen |
| `/creators` | Directory | SSR, indexable |
| `/creators/[handle]` | Creator page | Canonical public identity |
| `/creators/[handle]/support` | Tip / support | Auth for payment |
| `/creators/[handle]/releases/[id]` | Release detail | Optional; can reuse album page |
| `/charts` | Add creator charts tab | Existing route |
| `/community` | Challenges + spotlights | Replace mock data |

### 3.2 Creator Studio

| Route | Purpose |
|---|---|
| `/creator` | Overview: next action, recent activity, earnings snapshot |
| `/creator/releases` | All releases with status filters |
| `/creator/releases/new` | Publish wizard |
| `/creator/releases/[id]` | Release detail / edit / analytics |
| `/creator/analytics` | Metrics dashboard |
| `/creator/audience` | Followers + geography + sources |
| `/creator/earnings` | Ledger, by source, by month |
| `/creator/payouts` | Payout history, account, KYC |
| `/creator/profile` | Public page editor |
| `/creator/verification` | Application status + evidence |
| `/creator/opportunities` | Challenges, briefs, editorial calls |
| `/creator/settings` | Notifications, language, danger zone |

### 3.3 Admin (`admin_portal`)

| Route | Purpose |
|---|---|
| `/creators` | Creator CRM list |
| `/creators/[id]` | Creator detail + timeline |
| `/creators/applications` | Application queue |
| `/creators/verification` | Identity review queue |
| `/creators/releases` | Release review queue |
| `/creators/moderation` | Reports, strikes, appeals |
| `/creators/royalties` | Policy + period close + simulation |
| `/creators/payouts` | Payout runs + reconciliation |
| `/creators/fraud` | Anomalies + quarantine |
| `/creators/settings` | Thresholds, weights, fees, templates |

### 3.4 Redirects

| Old | New |
|---|---|
| `/artist-program` | `/creator-program` (301) |
| `/artist-dashboard` | `/creator` (302 until migration complete) |
| `/artist/[id]` | `/creators/[handle]` (301 when handle exists; otherwise 404) |

---

## 4. Public features

### 4.1 `/creator-program` — landing

**Goal:** explain the program in 15 seconds and convert the right people.

**Sections**

1. Hero: headline, subhead, primary CTA "Apply to the Creator Program", secondary "See creators".
2. Proof strip: verified creators, tracks published, paid to creators this month (only real numbers; hide until true).
3. "How it works" — 4 steps: Create → Publish → Get verified → Earn.
4. "What you get" — page + badge, analytics, follows, earnings, editorial.
5. "How you get paid" — Fund + tips + downloads; link to Royalty Policy.
6. "What we expect" — originality, rights, community rules.
7. FAQ — eligibility, fees, timing, AI disclosure, tax.
8. Final CTA + "Talk to the team" (mailto or form).

**Rules**

- No income guarantees.
- All numbers dated and sourced.
- Khmer and English copy.

### 4.2 `/creator-program/apply` — application

**Flow:** 4 steps, save-and-resume, autosave.

| Step | Fields | Validation |
|---|---|---|
| 1. Identity | Display name, handle, country, city, genres (max 3), AI disclosure | Handle availability, reserved names, profanity |
| 2. Links | Up to 5 links (YouTube, TikTok, Facebook, Instagram, website) | URL format; at least 1 external link |
| 3. Evidence | 3 track picks (from library), short pitch (500 chars), rights attestation checkbox | Tracks must be owned; attestation required |
| 4. Review | Summary + consent to Creator Agreement + submit | Explicit consent |

**States:** draft, submitted, in_review, changes_requested, approved, rejected.

**Post-submit:** confirmation screen with SLA, what happens next, link to status page.

**Edge cases:** duplicate application (block, show status), account too new (<30 days for Verified; allow Creator tier), suspended account (block), existing handle taken (suggest alternatives).

### 4.3 `/creators` — directory

**Layout**

- Header: "Creators" + search.
- Filters: genre, country, verified only, AI disclosure, sort (monthly listeners, newest, trending).
- Featured shelf (editorial, labeled).
- Grid: avatar, name, badge, genres, monthly listeners, follow button.
- Pagination + infinite scroll fallback.

**Rules**

- Only `active` creators with ≥1 published release.
- No earnings or private data.
- Empty state: "No creators match. Try another genre."

### 4.4 `/creators/[handle]` — creator page

**Above the fold**

- Banner (16:9, safe area), avatar (1:1, 320px), name, badges, handle.
- Tagline, genres, location.
- Stats: monthly listeners, followers, releases.
- Actions: Play (top track), Follow, Support (if enabled), Share.
- Overflow menu: Report, Copy link.

**Sections**

1. **Top tracks** — 5, playable, with duration and play count.
2. **Releases** — grid, newest first; each card shows cover, title, year, track count.
3. **Playlists** — public playlists containing the creator.
4. **About** — bio, active since, influences, links.
5. **Support** — tip jar / downloads / booking (conditional).
6. **Similar creators** — 4.
7. **Footer** — report link, policy links.

**Behavior**

- Follow is optimistic and idempotent; logged-out users get a sign-in prompt and return to the page.
- Play starts a persistent player; never navigates away.
- Hover/focus states are visible; keyboard navigable.
- `?ref=` and UTM preserved for analytics.

**SEO**

- `<title>{name} — Camxora</title>`
- Meta description from tagline/bio.
- JSON-LD `MusicGroup` + `Person`.
- Canonical; `hreflang` km/en.
- OG image generated with name, avatar, top genre.

**Empty/edge states**

- No releases: hide top tracks/releases; show "First release coming soon" + follow.
- Unverified: no badge; no earnings language.
- Suspended: 404 or "unavailable" page; never leak reason.
- Deleted: 410 with "This creator is no longer available."

### 4.5 Follow

| Action | Behavior |
|---|---|
| Follow | Insert row, increment count (cached), toast "Following" |
| Unfollow | Delete row, decrement, toast |
| Self-follow | Button hidden |
| Blocked | 403 with generic message |
| Rate limit | 60 follows/hour |
| Notification | Batched new-release email/in-app; opt-out in settings |
| Counts | Public; follower list private by default |

### 4.6 Support / tips

**Flow**

1. Click Support → sheet with suggested amounts and message.
2. Choose amount + method (KHQR, Chmaba, card).
3. Confirm fee breakdown ("Creator receives $2.70 of $3.00").
4. Pay → success → optional public supporter badge (default off).
5. Creator notified; earnings ledger entry created as `pending`.

**Rules**

- $1–$500; 90/10 split; fee shown before payment.
- Non-refundable except fraud/duplicate.
- Requires auth; no anonymous tips.
- Creator must have KYC before funds become available (tips can accrue before).

---

## 5. Creator Studio

### 5.1 `/creator` — overview

**Purpose:** answer "what should I do next?"

**Cards**

1. **Next action** — contextual: complete profile, submit verification, fix a release, set up payout, publish first track.
2. **Snapshot** — monthly listeners, valid streams (28d), followers, available balance.
3. **Recent releases** — status + quick actions.
4. **Notifications** — last 5.
5. **Program status** — tier, badge, verification state, KYC state.

**Empty state:** onboarding checklist with 5 steps and progress.

### 5.2 `/creator/releases`

**Table columns:** cover, title, type, status, release date, valid streams, earnings, actions.

**Filters:** all, draft, in review, changes requested, scheduled, published, taken down.

**Bulk actions:** submit, schedule, unpublish (with confirmation).

**Row actions:** edit, view public page, duplicate, analytics, takedown request.

### 5.3 `/creator/releases/new` — publish wizard

**Step 1 — Source**

- Pick a generation from the library (searchable, filter by ready).
- Choose variant (Version 1 / Version 2).
- Preview audio + waveform.
- If the generation is not ready, show status and disable next.

**Step 2 — Release details**

- Title (required, 1–100).
- Release type: single / EP / album.
- Cover art (required, ≥1400×1400; auto-crop; safety check).
- Primary genre (required, from catalog), secondary genres (max 2).
- Language (required), explicit flag.
- Release date (now or scheduled).
- Lyrics (optional, prefilled from generation).
- Description (optional, 500 chars).

**Step 3 — Credits & rights**

- Primary artist (default: creator).
- Featured artists (names + optional user handles).
- Songwriter / producer / lyricist (free text in v1).
- Collaborator split notice (v1: single payee attestation).
- Rights attestation: owns/cleared samples, vocals, lyrics, artwork.
- AI disclosure: original / AI-assisted / AI-generated.
- Voice consent confirmation if a cloned voice is used.
- Distribution scope: Camxora only (default) / Partner DSP (if enabled).

**Step 4 — Review & submit**

- Summary card.
- Checklist: metadata complete, cover valid, rights attested, policy read.
- Submit → status `submitted`; show SLA and next steps.

**Edge cases:** duplicate title (warn), duplicate audio (block after fingerprint ships), cover too small (block), scheduled date in past (warn), generation deleted (block), rights checkbox unchecked (block).

### 5.4 `/creator/releases/[id]`

- Header: cover, title, status chip, public link.
- Tabs: Overview, Tracks, Analytics, Credits, Review history.
- Overview: metadata, release date, visibility, actions (edit, submit, schedule, unpublish).
- Review history: submitted/changes/approved with reviewer notes and timestamps.
- Takedown: reason, status, appeal link.

### 5.5 `/creator/analytics`

**Header:** date range (7/28/90/12m/custom), comparison toggle, export CSV.

**KPI strip:** plays, valid streams, unique listeners, saves, followers, completion rate, RPM.

**Charts**

1. Trend line: plays vs valid streams vs listeners.
2. Top tracks table: title, plays, valid streams, saves, completion, earnings.
3. Traffic sources: discover, search, profile, playlist, chart, external, direct.
4. Geography: country (hidden below 100 listeners).
5. Device: mobile/desktop/tablet.
6. Release performance: first 7/28 days vs previous release.

**Rules**

- Every metric has an info tooltip with the definition and freshness.
- "Final after 48h" label.
- No earnings shown here; link to Earnings.
- Empty state: "Publish a release to see analytics" + CTA.

### 5.6 `/creator/audience`

- Followers over time.
- Top countries/cities (thresholded).
- Follow sources (profile, release page, external).
- New vs returning listeners.
- Follower list (private; creator sees aggregate only at launch).
- Export (Phase 4).

### 5.7 `/creator/earnings`

**Sections**

1. **Available balance** + next payout date + "Request payout" (disabled below threshold).
2. **This month** — accrued, pending, held, estimated.
3. **Breakdown** — royalty, tips, downloads, marketplace, adjustments (pie/bar).
4. **Ledger table** — date, source, description, gross, fee, net, status.
5. **Statements** — monthly PDF/CSV downloads.
6. **Policy summary** — rate, weights, caps, holdback; link to full policy.

**Rules**

- Never show another creator's data.
- Negative adjustments explained with a link to the dispute.
- Estimated amounts labeled "estimate" until the period locks.

### 5.8 `/creator/payouts`

**Sections**

1. **Payout account** — method, masked account, status (unverified/verified/rejected), edit.
2. **KYC** — status, required docs, start/resume.
3. **Payout history** — period, amount, status, reference, statement.
4. **Tax** — TIN status, annual statements.
5. **Help** — what to do if a payout fails.

**States:** not started, pending review, verified, rejected (reason + resubmit), frozen (fraud/strike).

### 5.9 `/creator/profile`

- Live preview of the public page beside the form.
- Fields: avatar, banner, display name, handle, tagline, bio, genres, location, links, AI disclosure, support settings.
- Validation inline; save draft vs publish.
- Handle change: warning, 90-day cooldown, redirect notice.
- Image upload: crop, size, format, safety scan.

### 5.10 `/creator/verification`

- Current tier + badge.
- Checklist: profile complete, 3 releases, account age, rights attestation, external link.
- Application status timeline.
- Evidence upload (ID, selfie, business registration) — encrypted.
- "Why we ask" explanations.
- Appeal link if rejected.

### 5.11 `/creator/opportunities`

- Weekly challenge card (brief, deadline, prize, entries, submit).
- Editorial calls ("Khmer pop playlist submissions").
- Brand briefs (Phase 4).
- Past entries + results.

### 5.12 `/creator/settings`

- Notification preferences (email/in-app per event).
- Language (English/Khmer).
- Currency display (USD/KHR).
- Connected accounts (future).
- Danger zone: leave program, delete account, export data.

---

## 6. Admin console

### 6.1 Creator CRM

- Table: avatar, name, handle, tier, status, country, verified, KYC, earnings, strikes, last active.
- Filters: tier, status, country, KYC, payout status, has strikes.
- Search by name, handle, email, user ID.
- Detail page: profile summary, timeline (applications, releases, reports, payouts), notes, actions (verify, suspend, message, adjust earnings).

### 6.2 Application queue

- Columns: applicant, submitted, SLA due, tier requested, evidence completeness, status.
- Detail: answers, links, track previews, automated checks, duplicate detection, notes.
- Actions: approve, request changes (template), reject (reason), escalate.
- Bulk assign; SLA timer color.

### 6.3 Verification queue

- Identity docs viewer with zoom, redaction, and access logging.
- Match checks: name vs bank, selfie vs ID, external links.
- Actions: approve, reject, request resubmission.
- Expiry tracking (12 months).

### 6.4 Release queue

- Pending list with audio player, metadata diff, cover preview, auto-check results.
- Actions: approve, request changes, reject, schedule.
- Policy checklist visible.

### 6.5 Moderation

- Reports inbox: subject, reason, reporter, age, priority.
- Strike panel: history, severity, expiry.
- Appeals: original decision, appeal text, different reviewer, decision.
- Bulk actions with confirmation.

### 6.6 Royalty console

- Current policy card (version, effective date, pool, weights, caps).
- **Simulation**: upload last month's data → preview payouts, top creators, cap impact, pool distribution.
- Period list: open, calculated, locked, paid.
- Actions: calculate, recalculate (with reason), lock, export.
- Audit log of policy changes.

### 6.7 Payout console

- Run list: period, total, creators, status, created by.
- Run detail: line items, failed accounts, reconciliation summary.
- Maker-checker: "Approve" disabled for the creator; "Mark paid" requires reference.
- Export bank batch (CSV per rail).
- Statements generation.

### 6.8 Fraud console

- Alerts: velocity, concentration, device graph, VPN, owner-play anomalies.
- Detail: listener table (hashed IDs), IP/device clusters, timeline.
- Actions: quarantine, exclude streams, hold earnings, clawback, suspend, dismiss.
- Clawback requires finance approval above $50.

### 6.9 Settings

- Fund floor/share/cap/reserve.
- Weights per origin.
- Caps per track/creator.
- Eligibility thresholds.
- Payout minimum, holdback days, rails.
- Fee percentages.
- Email templates and sender identities.

---

## 7. Shared components

| Component | Used by | Requirements |
|---|---|---|
| `CreatorBadge` | Public, Studio, Admin | Icon + tooltip; accessible label; variants |
| `CreatorAvatar` | All | Fallback initials; size scale; lazy load |
| `FollowButton` | Public | Optimistic, idempotent, auth-aware, rate-limited |
| `PlayButton` | Public | Persistent player, keyboard accessible |
| `ReleaseCard` | Public, Studio | Cover, title, year, status; skeleton |
| `MetricCard` | Studio | Value, delta, definition tooltip, freshness |
| `TipSheet` | Public | Amount, method, fee breakdown, success |
| `StatusChip` | All | Consistent colors and labels |
| `EmptyState` | All | Icon, explanation, primary CTA |
| `ConfirmDialog` | All | Destructive actions, reason field |
| `DataTable` | Admin | Sort, filter, pagination, bulk select, sticky header |

---

## 8. Notifications & emails

| Event | Channel | Timing | Content |
|---|---|---|---|
| Application received | In-app + email | Immediate | SLA, next steps, status link |
| Changes requested | In-app + email | Immediate | What to fix, resubmit link |
| Approved / rejected | In-app + email | Immediate | Badge, reason, appeal link |
| Release submitted | In-app | Immediate | SLA |
| Release approved / changes / rejected | In-app + email | Immediate | Notes, public link |
| New follower | In-app | Batched daily | Count, not individual identities |
| New release from followed creator | In-app + email | Immediate | Track, play link, unfollow |
| Tip received | In-app + email | Immediate | Amount, supporter (optional) |
| Payout statement ready | Email | Monthly | PDF/CSV, amount, date |
| Payout sent / failed | In-app + email | Immediate | Reference, amount, next step |
| Earnings adjustment | In-app + email | Immediate | Reason, amount, dispute link |
| Strike / suspension | In-app + email | Immediate | Reason, duration, appeal |
| Challenge result | In-app + email | On results | Placement, prize |
| Policy change | Email | 30 days before | Summary, effective date |
| KYC expiring | In-app + email | 30/7 days before | Resubmit link |

**Preferences:** per event, email/in-app toggles; transactional emails cannot be fully disabled.

---

## 9. States, errors, and edge cases

### 9.1 Global

- Loading: skeleton, never blank.
- Empty: explanation + CTA.
- Error: human message + retry; no stack traces.
- Offline: banner; queue actions where safe.
- Rate limited: show wait time.

### 9.2 Creator edge cases

| Case | Behavior |
|---|---|
| Handle taken | Suggest 3 alternatives |
| Handle change within 90 days | Disabled with date |
| Profile incomplete | Block verification; show checklist |
| No releases | Hide releases; show onboarding |
| Release rejected | Show reason; allow edit + resubmit |
| Account suspended | Hide page; block publishing; allow appeal |
| KYC rejected | Show reason; allow one resubmission |
| Payout below threshold | Disabled; show amount needed |
| Payout account mismatch | Block; explain name match |
| Duplicate audio | Block publish; explain |
| Explicit content | Require flag; age gate |
| AI disclosure mismatch | Warn; review; possible strike |
| Copyright report | Freeze earnings; notify; appeal |
| Deleted generation | Block publish; ask to recreate |

### 9.3 Listener edge cases

| Case | Behavior |
|---|---|
| Logged-out follow | Prompt sign-in, return to page |
| Logged-out tip | Prompt sign-in |
| Creator blocked | Generic unavailable message |
| Creator suspended | 404/unavailable |
| Region-restricted track | Show unavailable, no error |
| Slow network | Prefetch next track; show buffering |

---

## 10. Accessibility & localization

- WCAG 2.2 AA: contrast, focus rings, keyboard nav, labels, reduced motion.
- Screen-reader labels for badges, play state, follow state.
- Khmer (`km`) and English (`en`) UI; number/date formatting per locale.
- Khmer line-height and font fallback tested.
- All legal documents available in Khmer.
- Currency toggle USD/KHR; amounts stored in micro-USD.
- RTL not required at launch.

---

## 11. Acceptance criteria (feature-level)

### A1 — Public creator page

- [ ] Loads server-rendered with real data for an active creator.
- [ ] Shows name, badge, stats, top tracks, releases, about, follow.
- [ ] Follow/unfollow works for authenticated users; counts update.
- [ ] Logged-out follow prompts sign-in and returns to page.
- [ ] Suspended creator returns 404; deleted returns 410.
- [ ] JSON-LD validates; OG image renders.
- [ ] LCP < 2s on throttled 4G; Lighthouse a11y ≥ 95.

### A2 — Application

- [ ] Draft saves and resumes.
- [ ] Handle availability checks live.
- [ ] Required evidence blocks submit.
- [ ] Submitting creates an application and shows SLA.
- [ ] Duplicate application is blocked with status link.
- [ ] Admin sees the application in the queue within 60s.

### A3 — Publish

- [ ] Creator can pick a ready generation and variant.
- [ ] Metadata validation blocks incomplete submissions.
- [ ] Cover upload validates dimensions and safety.
- [ ] Rights attestation is mandatory.
- [ ] Submission creates a release in `submitted`.
- [ ] Admin approve publishes to the catalog and the public page.
- [ ] Changes requested returns to the creator with notes.
- [ ] Unpublish removes from public surfaces within 60s.

### A4 — Analytics

- [ ] Metrics match the definitions for a seeded dataset.
- [ ] Owner plays excluded.
- [ ] Duplicate streams deduped.
- [ ] Date filters and comparisons work.
- [ ] CSV export matches the table.
- [ ] Empty state is actionable.

### A5 — Earnings

- [ ] Ledger entries sum to the displayed balance.
- [ ] Royalty calculation matches the policy simulation.
- [ ] Caps and weights applied exactly.
- [ ] Adjustments appear as separate entries.
- [ ] Statements match the ledger to the cent.
- [ ] No other creator's data is accessible (IDOR test).

### A6 — Payouts

- [ ] Payout blocked below threshold.
- [ ] Payout blocked without verified KYC and account.
- [ ] Maker-checker enforced (same user cannot approve and pay).
- [ ] Mark-paid requires a reference.
- [ ] Failed payouts retry and notify.
- [ ] Reconciliation report shows zero unexplained difference.

### A7 — Moderation

- [ ] Report creates a queue item with SLA.
- [ ] Strike applies the correct restriction.
- [ ] Appeal routes to a different reviewer.
- [ ] Every action is audit-logged.
- [ ] Suspended creator disappears from public surfaces.

---

## 12. Sample data pack (deferred)

A fictional sample catalog is specified in [SAMPLE_CREATORS.md](./SAMPLE_CREATORS.md). It is **not seeded at launch** and is not a launch dependency.

**What it contains**

- 8 fictional creators across Khmer pop, hip hop, R&B, ballad, EDM, traditional fusion, lo-fi, and rap.
- 10 releases: 3 pop albums × 10 tracks, plus 7 EPs × 5 tracks = **65 tracks**.
- Khmer-first lyrics (`language: km`), original per-album prompts, and a documented SLai avatar plan.

**What it is for**

- QA and design review once identity/publishing exist.
- Demo and marketing pages (clearly labeled “Sample creator”).
- Visual and content testing for creator pages, releases, and analytics.

**Rules**

- Never present sample creators as real people.
- Tag every sample row and provide a one-command removal script.
- Do not run the seed in production.
- Replace placeholder avatars with SLai output only when a valid key is configured.
- A native Khmer reviewer must approve public lyrics.

**Why deferred**

- The tables it seeds (`creator_profiles`, `creator_releases`, `stream_*`) do not exist yet.
- The local SLAI key is invalid (`AUTH_002`), so real avatars cannot be generated now.
- Real audio for 65 tracks costs credits and depends on the generation pipeline.
- None of this blocks the program; it ships with Phase 4.

---

## 13. Copy and tone

- Direct, warm, honest. No hype.
- Never promise income.
- Explain fees before payment.
- Use "creator" not "artist" in program copy; "artist" remains a music credit.
- Khmer copy reviewed by a native speaker, not machine-translated only.
- Error messages say what happened and what to do next.
