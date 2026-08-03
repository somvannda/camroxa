# Phase 0 API capacity — workers, pool, lighter progress polls

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/api-phase0-capacity`

## Problem

Desktop timeouts (`Request timed out contacting api.camxora.com`) while portals stayed up. Host RAM/CPU were fine; **2 uvicorn workers** were saturated by batch/image work plus frequent heavy `GET /progress` (which re-ran `ensure_batch_image_jobs` for every batch on every poll). Desktop httpx default timeout is 30s.

## Phase 0 changes

### Server
- uvicorn workers **2 → 4** (live systemd + provision script default)
- asyncpg pool **min_size=4, max_size=8** (≤32 conns with 4 workers)
- `/progress` only calls `ensure_batch_image_jobs` for batches that **have no image_jobs rows**

### Desktop (needs rebuild/restart to pick up)
- Progress poll: idle **45s**, active **15s** (was 30s / 8s)
- Video pipeline poll: **12s** (was 6s)
- Local progress sync: **30s** (was 20s)
- Coordinator poll limit **40** (was 80)
- `/progress` timeout **90s**; `/settings` + `/profiles` **60s**
- One automatic retry on GET timeout

## Out of scope (Phase 1)
Job queue + dedicated `platform_worker` (move BackgroundTasks off HTTP workers).
