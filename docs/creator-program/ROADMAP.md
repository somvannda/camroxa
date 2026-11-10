# Camxora Creator Program — Roadmap & Execution Plan

**Version:** 1.0 (proposal)
**Date:** 2026-11-09
**Related:** [README](./README.md) · [BRD](./BRD.md) · [Product Spec](./PRODUCT_SPEC.md) · [Technical Design](./TECHNICAL_DESIGN.md)

---

## 1. How to read this plan

- Durations assume **2 backend engineers, 1 frontend engineer, 1 designer (50%), 1 ops/moderation lead (50%), and legal/finance review in parallel**.
- Phases are gated: do not start the next phase until the exit criteria are met.
- The **Studio agent owns generation/editing**. This plan owns identity, publishing, analytics, earnings, and payouts. They can run in parallel after the interface contract is agreed.
- Dates are relative to kickoff, not calendar promises.

---

## 2. Phase plan

### Phase 0 — Foundation & decisions (Week 0–1)

**Goal:** remove blockers and make the business decisions that everything else depends on.

| # | Deliverable | Owner | Notes |
|---|---|---|---|
| 0.1 | Decision workshop: name, tiers, fund budget, AI weighting, launch model | Product | Use BRD §18; record decisions |
| 0.2 | Legal kickoff: Creator Agreement, Royalty Policy, Payout/Tax Policy | Legal/Finance | Tax counsel is the long pole |
| 0.3 | Migration 186: `valid_streams`, `royalty_ledger`, `royalty_policies`, `royalty_periods`, `stream_tracks.origin` | Backend | Fixes B1–B4 |
| 0.4 | Implement `RoyaltyPolicyService` + fix `streaming_admin` endpoint | Backend | Admin catalog must return 200 |
| 0.5 | Metric definitions signed off (play, valid stream, royalty stream, unique listener) | Product + Data | One source of truth |
| 0.6 | Remove or label fictional artists on public pages | Frontend | Trust blocker |
| 0.7 | Freeze the Studio ↔ Creator interface contract | Both agents | See §4 |
| 0.8 | Sandbox seed data: 10 creators, 50 tracks, 100k listen events | Backend | For testing |

**Exit criteria**

- [ ] Decisions recorded and signed.
- [ ] Migration 186 applied in sandbox.
- [ ] Admin catalog endpoint returns 200 with real numbers.
- [ ] Fake artists removed or flagged.
- [ ] Interface contract documented.
- [ ] Legal drafts in review.

**Parallel with Studio:** yes, almost entirely.

---

### Phase 1 — Identity & program (Week 2–4)

**Goal:** real creators, real pages, real applications.

| # | Deliverable | Surface |
|---|---|---|
| 1.1 | Migrations 187–189: profiles, handles, applications, verifications, badges, follows | DB |
| 1.2 | Profile editor + handle claim + validation | Studio |
| 1.3 | Public creator page `/creators/[handle]` | Web |
| 1.4 | Creator directory `/creators` | Web |
| 1.5 | Program landing + application flow `/creator-program` | Web |
| 1.6 | Follow/unfollow + counts | Web/API |
| 1.7 | Admin creator CRM + application queue + verification queue | Admin |
| 1.8 | Badge grant/revoke + audit | Admin |
| 1.9 | Redirects: `/artist-program`, `/artist/[id]`, `/artist-dashboard` | Web |
| 1.10 | SEO: JSON-LD, OG images, sitemap | Web |
| 1.11 | Khmer copy for program + profile | Web |

**Exit criteria**

- [ ] A creator can claim a handle, complete a profile, and see a public page.
- [ ] A listener can follow/unfollow; counts update.
- [ ] An admin can approve an application and grant a badge.
- [ ] No fictional artist data remains on public surfaces.
- [ ] Lighthouse a11y ≥ 95, LCP < 2s on throttled 4G.
- [ ] 10 closed-beta creators onboarded.

**Parallel with Studio:** yes. Studio can link to `/creator/profile` and `/creator/verification`.

---

### Phase 2 — Publishing, analytics, moderation (Week 5–7)

**Goal:** creators can release music, see honest numbers, and trust the platform.

| # | Deliverable | Surface |
|---|---|---|
| 2.1 | Migrations 190–192, 195: releases, credits, listen events, stats, moderation | DB |
| 2.2 | Publish wizard (4 steps) + draft/edit/submit | Studio |
| 2.3 | Admin release review queue | Admin |
| 2.4 | Publish to `stream_albums`/`stream_tracks` + public page refresh | API |
| 2.5 | Listen event ingestion + validation + dedupe | API |
| 2.6 | Daily stats rollups + analytics dashboard | Studio |
| 2.7 | Audience dashboard | Studio |
| 2.8 | Reports + moderation queue + strikes + appeals | Web/Admin |
| 2.9 | Notifications + lifecycle emails | API |
| 2.10 | Release scheduling + follower notifications | API |
| 2.11 | CSV analytics export | Studio |
| 2.12 | Studio integration: "Publish" button + deep link | Studio agent |

**Exit criteria**

- [ ] Creator publishes a generation → admin approves → it appears on the public page and catalog.
- [ ] Analytics match seeded definitions; owner/duplicate/fraud excluded.
- [ ] A report creates a queue item and a strike applies correctly.
- [ ] Emails fire for application, release, and payout events.
- [ ] 25 creators publishing; 100 releases.

**Parallel with Studio:** partial. The Studio agent should implement the "Publish" entry point against the contract in §4 early in this phase.

---

### Phase 3 — Money (Week 8–11)

**Goal:** pay creators correctly, on time, with a ledger that reconciles.

| # | Deliverable | Surface |
|---|---|---|
| 3.1 | Migrations 193–194, 196: earnings, KYC, payout accounts, payouts, tips | DB |
| 3.2 | Royalty engine + policy simulation + period close/lock | API |
| 3.3 | Earnings dashboard + statements (PDF/CSV) | Studio |
| 3.4 | KYC flow + encryption + admin review | Studio/Admin |
| 3.5 | Payout account + verification + cooling period | Studio |
| 3.6 | Payout run + maker-checker + mark-paid + reconciliation | Admin |
| 3.7 | Tips (KHQR/Chmaba) + 90/10 split + earnings integration | Web/API |
| 3.8 | Fraud console + quarantine/clawback | Admin |
| 3.9 | Royalty policy page + current rate publication | Web |
| 3.10 | Finance runbook + two sandbox cycles | Finance |

**Exit criteria**

- [ ] Royalty calculation passes all invariants; simulation equals actual.
- [ ] Two sandbox payout cycles reconcile to $0.00.
- [ ] KYC + payout account + TIN captured and encrypted.
- [ ] Maker-checker enforced; same user cannot approve and pay.
- [ ] Statement matches ledger to the cent.
- [ ] Fraud console catches a seeded farm.

**Parallel with Studio:** mostly independent; Studio only needs the earnings links.

---

### Phase 4 — Expansion (Week 12–16)

**Goal:** increase creator income and differentiation.

| # | Deliverable |
|---|---|
| 4.1 | Collaborator credits + split payouts (invite/accept, escrow) |
| 4.2 | Paid downloads + commercial licenses |
| 4.3 | Sample/prompt pack marketplace |
| 4.4 | Services / booking leads |
| 4.5 | Weekly challenges + judging + prizes |
| 4.6 | Creator charts + genre charts |
| 4.7 | Partner tier + roster pilot |
| 4.8 | Creator digest + annual statement |
| 4.9 | Sample creator pack: seed 8 fictional creators + 65 Khmer-first tracks, replace placeholder avatars with SLai output, label as demo |

**Exit criteria**

- [ ] A collaborator can accept a split and be paid independently.
- [ ] A download purchase credits the creator and appears in earnings.
- [ ] A challenge runs end-to-end with winners paid in credits.
- [ ] Partner pilot signed with 1–3 creators/labels.

---

### Phase 5 — Scale (post-launch)

- Creator subscriptions.
- Brand briefs / campaigns.
- Embeddable player.
- Partner API for labels.
- DSP distribution.
- Mobile app surfaces.
- Fraud ML model.
- Multi-language expansion (Thai, Vietnamese).

---

## 3. Critical path

```
Decisions + legal ──► Migration 186 + RoyaltyPolicyService ──► Identity (P1)
                                                              │
                                                              ▼
                                          Publishing + analytics (P2)
                                                              │
                                                              ▼
                                          Earnings + KYC + payouts (P3)
                                                              │
                                                              ▼
                                                    First payout (gate)
```

**Long poles**

1. **Legal/tax sign-off** (start Week 0; can block Phase 3).
2. **Royalty policy decisions** (fund size, weights, caps, thresholds).
3. **KYC/payout rails** (bank integration, name matching).
4. **Moderation capacity** (hiring/training, not code).
5. **Studio integration** (publish button, deep link).

---

## 4. Studio ↔ Creator Program interface contract

**Principle:** Studio generates; Creator Program publishes. No shared table writes.

| Direction | Call | Payload |
|---|---|---|
| Studio → Creator | `POST /api/v3/creator/me/releases` | `{source:{type:"web_music_generation",task_id,variant}, metadata:{...}}` |
| Creator → Studio | Deep link | `/studio/editor?task_id=...&variant=...` |
| Creator → Studio | Open library picker | `GET /api/v3/web-music/generations?ready=true` |
| Shared UI | Components | `CreatorBadge`, `CreatorAvatar`, `FollowButton`, `ReleaseCard` |

**Rules**

- Studio must not write `creator_*`, `royalty_*`, `payout_*`, `stream_albums`, or `stream_tracks`.
- Studio must not create its own release metadata schema.
- Publish is idempotent on `(task_id, variant)`.
- Creator Program returns `release_id` + `status`; Studio routes to `/creator/releases/[id]`.
- Coordinate migration numbers: Creator Program reserves **186–199**.

---

## 5. Workstreams and ownership

| Workstream | Owner | Phase |
|---|---|---|
| Product decisions + policy | Product | 0–3 |
| Legal/tax | Legal/Finance | 0–3 |
| Schema + services | Backend | 0–4 |
| Public web | Frontend | 1–3 |
| Creator Studio | Frontend | 1–4 |
| Admin consoles | Frontend/Backend | 1–4 |
| Moderation ops | Trust & Safety | 1–4 |
| Finance ops | Finance | 3–4 |
| Community/challenges | Community | 4 |
| Analytics/warehouse | Data | 2–3 |

---

## 6. Sprint-level breakdown (first 8 weeks)

### Sprint 1 (Week 1)

- Decisions workshop; decision log.
- Migration 186 + `RoyaltyPolicyService`.
- Fix admin catalog.
- Remove fake artists.
- Studio contract agreed.
- Legal drafts started.

### Sprint 2 (Week 2)

- Profiles + handles + profile editor.
- Handle validation + reserved list.
- Public page shell.
- Admin CRM skeleton.

### Sprint 3 (Week 3)

- Public page full (tracks, releases, about, follow).
- Directory + search.
- Application flow.
- Verification queue.

### Sprint 4 (Week 4)

- Badges + audit.
- Redirects + SEO.
- Khmer copy.
- Closed beta onboarding (10 creators).

### Sprint 5 (Week 5)

- Release schema + publish wizard.
- Admin release queue.
- Publish to catalog.
- Studio publish button.

### Sprint 6 (Week 6)

- Listen events + validation.
- Rollups + analytics dashboard.
- Notifications.

### Sprint 7 (Week 7)

- Audience dashboard.
- Moderation + strikes + appeals.
- CSV export.
- Analytics QA vs definitions.

### Sprint 8 (Week 8)

- Earnings schema + royalty engine.
- Policy simulation.
- KYC flow.
- Finance dry run.

---

## 7. Acceptance gates (summary)

| Gate | Phase | Pass criteria |
|---|---|---|
| G0 Foundation | 0 | Admin catalog 200; migration 186; decisions signed |
| G1 Identity | 1 | 10 creators with real pages; follows work; no fake data |
| G2 Publishing | 2 | 25 creators; 100 releases; analytics validated |
| G3 Money | 3 | Two sandbox cycles reconcile; KYC + maker-checker |
| G4 Public launch | 3 | Legal signed; Khmer; a11y; runbooks; support trained |
| G5 Scale | 4 | Splits, downloads, marketplace, challenges live |

---

## 8. Resourcing estimate

| Role | Effort | Notes |
|---|---|---|
| Backend | 2 FTE × 12 weeks | Schema, services, royalty engine, payouts |
| Frontend | 1 FTE × 12 weeks | Public + Studio + admin |
| Designer | 0.5 FTE × 8 weeks | Pages, components, Khmer typography |
| Ops/Moderation | 0.5 FTE from Week 1 | Applications, releases, reports |
| Finance | 0.5 FTE from Week 6 | Policy, payouts, reconciliation |
| Legal | External | Contracts, tax, copyright |
| Data | 0.25 FTE | Metric definitions, validation |

**Total:** roughly **24 engineer-weeks** for Phases 0–3 (launch), plus **12–16** for Phase 4.

---

## 9. What to do this week (concrete)

1. **Approve or change the 10 decisions** in [BRD §18](./BRD.md#18-open-decisions-need-answers-before-phase-1). Default recommendations are safe.
2. **Assign owners**: product, backend lead, frontend lead, ops/moderation, finance.
3. **Start legal**: Creator Agreement + Royalty Policy + Payout/Tax Policy.
4. **Ship migration 186** and fix the admin catalog endpoint (B1–B4). This is a 1–2 day fix and unblocks everything.
5. **Agree the Studio contract** with the other agent (§4 above).
6. **Remove fictional artists** from public pages or label them demo.
7. **Do not seed the sample creator pack yet.** It is a Phase 4 demo asset; the fixture lives in `docs/creator-program/sample-creators/` and is documented in [SAMPLE_CREATORS.md](./SAMPLE_CREATORS.md).
7. **Pick 10 beta creators** and interview them with the BRD questions:
   - What would make you publish here instead of YouTube/SoundCloud?
   - What would you expect to earn in month 1?
   - What would make you trust the payout?
   - What would make you leave?

---

## 10. Open decisions log

| # | Decision | Recommendation | Status | Owner | Date |
|---|---|---|---|---|---|
| 1 | Program name | Camxora Creator Program | Proposed | Product | — |
| 2 | Launch model | Closed beta (50) → open | Proposed | Product | — |
| 3 | Fund floor | $3,000/month for 6 months | Proposed | Finance | — |
| 4 | Pay AI-generated? | Yes, 0.3 weight, capped | Proposed | Product | — |
| 5 | Tips at launch | Yes, Phase 3 | Proposed | Product | — |
| 6 | Downloads at launch | Phase 4 | Proposed | Product | — |
| 7 | KYC vendor | Manual first, vendor at 500 | Proposed | Ops | — |
| 8 | Payout entity | Registered Cambodian entity | Proposed | Finance | — |
| 9 | Verification bar | 3 tracks or 500 valid streams + external link | Proposed | Product | — |
| 10 | Splits | Metadata-only v1; splits Phase 4 | Proposed | Product | — |

---

## 11. Post-launch review (30/60/90 days)

**30 days**

- Funnel: applications → approvals → publishes → first stream.
- Payout accuracy and support tickets.
- Fraud alerts and false positives.
- Creator NPS (first 20 interviews).

**60 days**

- Retention: creators publishing a second release.
- Listener follow conversion.
- Earnings distribution: median, top 1%, Gini.
- Cost per verified creator.

**90 days**

- Decide: raise pool, change weights, open applications, launch downloads.
- Kill features nobody uses.
- Publish a public transparency report (creators paid, tracks published, fraud removed).
