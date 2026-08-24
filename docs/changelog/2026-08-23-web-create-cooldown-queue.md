# Web Create cooldown + submit queue

**Superseded by** [`2026-08-23-web-create-global-queue.md`](./2026-08-23-web-create-global-queue.md). The 12s / 3-song client queue cannot do paid-first across users.

**Date:** 2026-08-23  
**Surfaces:** music_web  
**Branch:** `feature/web-create-cooldown-queue`

## Summary

`music.camxora.com/create` treated Create as “busy only while the generate POST is in flight.” A local HTTP 500 in under a second re-enabled the button, so a user could charge-and-refund twice, then hit 429. Desktop already paces Suno at 20 submits / 10s and queues the rest. Web now does a short lock, then queues the next song instead of waiting for audio.

## Product impact

- First 2 seconds after Create: button stays **Creating…** and ignores extra clicks (double-tap / rage click).
- Next 12 seconds (or `Retry-After` if longer): button becomes **Queue next**. Another click snapshots the form and lines up that song. It does **not** wait for Version 1/2 to finish.
- At most **3** queued songs. Credits are reserved in the UI and charged only when that queued POST starts.
- Queued rows show at the top of the workspace list and can be removed before they start.
- Insufficient credits, geo-block, or generation freeze clear the queue.

## Technical impact

- `create-submit-queue.ts` owns cooldown, hard-lock, affordability, and button copy.
- `MusicApiError` carries HTTP status + `Retry-After` (header or `error.details.retry_after`).
- Drain runs after each generate attempt and on a 250ms tick. In-flight guard is a ref so React double-invokes cannot submit twice.

## Files touched

- `music_web/src/lib/create-submit-queue.ts`
- `music_web/src/lib/create-submit-queue.test.ts`
- `music_web/src/lib/web-music-api.ts`
- `music_web/src/components/create-page-client.tsx`
- `music_web/CHANGELOG.md`
- `docs/changelog/2026-08-23-web-create-cooldown-queue.md`

## Migration/deploy

Sandbox music web rebuild:

```bash
python scripts/deploy/rebuild_music_web_sandbox.py
```

No API, migration, or nginx change. Production only when asked.

## Tests

- `npx tsx --test music_web/src/lib/create-submit-queue.test.ts`
- Manual: Create once, confirm 2s lock then Queue next; queue a second song while the first is still Waiting; remove a queued row before it starts; 429 should extend the wait.

## Follow-ups

- Production music web rebuild after review.
- Optional: persist the queue across refresh (currently in-memory only).
