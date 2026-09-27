# Camxora Artist Royalty Program

Build a stream-accounting + anti-fraud + royalty system, not a play-count increment. The client only sends playback evidence; FastAPI decides whether a listen becomes a valid stream, then (after a hold) a royalty stream. Every threshold and rate lives in admin-editable policy. Payouts in v1 are admin-manual (creator requests withdraw, admin marks paid after bank/Wing/ABA).

Stay on FastAPI platform_api, Postgres, Redis, and platform_api.worker / job_queue. Do not add a Node playback API or Kafka.

Suggested branch: feature/artist-royalty-program.

## Two programs, one stack

Today every public catalog track is Suno AI owned by a Camxora user. v1 pays Camxora Creators (people who generated AI music). Real recording artists are designed in the same tables but stay off until Phase 6.

Camxora Creator (v1): origin=ai_generated; Creator Studio; AI rate table (stricter, 100k stream cap ~$60.25); $5 min withdrawal; admin royalty_verified.

Recording artist (Phase 6): origin=original_upload; same Studio/ledger/WS; Original rate table (1M cap ~$2370.50); program_enabled_original=false until Phase 6. DistroKid if it returns maps to original_upload.

Rule: royalties follow track origin, not a self-label. Cannot get Original rates on a Suno file.

Admin: program_enabled_ai (on at launch), program_enabled_original (off). Two rate tables. Phase 6 is a switch, not a rewrite.

## Gaps today

Play count is first bytes=0- Range, not 30s. Packaged tracks do not increment play_count. Heartbeats exist for DRM but send frozen bytes_served, not currentTime. No unique listeners. No artist ledger. All catalog is AI. Email verified is not KYC.

Do not feed stream_tracks.play_count into royalties.

## Valid stream (admin-editable)

Authenticated, email confirmed, license session, 30 seconds or 50% if track shorter than 60s, forward heartbeats, not owner, not admin, not high fraud.

Eligibility per track: 1000 valid streams in 365 days, 100 unique listeners (user_id), published, AI program on for v1, royalty_verified to withdraw. Streams before eligibility not paid.

Payout: eligible != withdrawable. $5 min. Monthly. Tiered rates not retroactive. AI cap 100k streams. Original cap 1M (stored, not paid until Phase 6).

Original default tiers (Phase 6, stored now): 0-999 $0; 1k-4999 $0.0005; 5k-9999 $0.0007; 10k-49999 $0.001; 50k-99999 $0.0015; 100k-499999 $0.002; 500k-999999 $0.0025; 1M+ $0. Examples: 5k=$2; 10k=$6.50; 100k=$120.50; 1M=$2370.50.

AI v1: 50% of those rates, 100k cap.

## Admin policy

royalty_policies versioned, Redis cache ~5s. Settings → Artist Royalties. Liability preview. Policy version on each accrual.

Also: analytics_lag_days default 1 (T-1 stats).

## Architecture

Reuse FastAPI content_license_service, rate_limit, job_queue, credit_transactions pattern, admin_pending_ops, existing /api/v1/ws. Not play_count, not CutLuy payout, not credit_wallets.

## Phases

Phase 1: origin flag, unify heartbeat with currentTime, valid_streams, unique listeners, play_source, Redis rt:track concurrent set, debounced studio.listeners on existing WS to owner only. Original program stays disabled.

Phase 2: admin AI+Original tables, enable AI only, T-1 rollups, 7-day hold, micro-USD ledger.

Phase 3: payout profiles, $5 min, admin-manual queue, dual-control. account_kind creator now.

Phase 3b: music_web Creator Studio from header dropdown (Profile, Creator Studio, Pricing, Sign out). Pages: /studio overview, earnings, tracks, audience, payouts. Discovery later. Official stats T-1. Listening now live unofficial via /api/v1/ws, REST poll fallback. Studio only, no public live badge.

Phase 4: fraud hardening, rules not ML.

Phase 5: Discovery/search analytics from play_source.

Phase 6 later: original uploads, stronger KYC, enable program_enabled_original. No upload UI in v1.

Three clocks: official stats yesterday; money 7-day hold; Listening now live unofficial.

## Studio pages

Overview: valid streams, unique listeners, listen time, estimated earnings pending vs settled, eligibility progress, top tracks, Listening now rail.

Earnings: available vs pending, RPM = settled USD / royalty streams * 1000 (effective, not raw rate table in client).

Audience: country from CF-IPCountry, platform, new vs returning. No subscribers.

Payouts: Wing/ABA/bank, request history.

Discovery later: play_source home/explore/search/genre/artist/album/playlist/share.

## Out of scope v1

CutLuy disburse, original upload UI, ISRC, splits, DistroKid, Node/Kafka/ML, Socket.IO, backfill old play_count, production deploy unless asked.
