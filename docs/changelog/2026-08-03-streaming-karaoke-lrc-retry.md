# Streaming karaoke LRC — retry Suno timestamps + backfill

**Date:** 2026-08-03  
**Status:** implemented  
**Branch:** `fix/streaming-karaoke-lrc-backfill`

## Problem

Music streaming karaoke (synced lyrics) disappeared for new tracks. Player needs LRC tags in `stream_tracks.lyrics`; without them it shows static plain lyrics.

Prod snapshot: **1365** tracks with lyrics, only **223** with LRC tags, and **0** of the LRC tracks had `suno_audio_id`. Recent tracks had `suno_audio_id` + `external_task_id` but plain lyrics. A live `get-timestamped-lyrics` call for a recent track returned **354 aligned words** and valid LRC — so Suno still has the data; we were not persisting it reliably.

## Cause

1. Upload fetches timestamps once, immediately after Suno completes — alignments are often empty for a short window; failure falls back to plain lyrics.
2. Admin MP3 upload retry path never fetched timestamped lyrics at all.

## Fix

- Retry `fetch_timestamped_lrc_with_pool` (default 4 attempts, 2s apart)
- Admin retry path now fetches LRC the same way as the primary upload path
- One-shot backfill script for existing recoverable tracks

## Surfaces

| Surface | Change |
|---------|--------|
| platform_api | LRC retry + retry-path fix |
| music streaming | karaoke returns for new uploads; backfill restores older ones |
