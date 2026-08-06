# Heal Suno success rows missing audio_url when audio_id exists

**Date:** 2026-08-06  
**Surfaces:** `platform_api`  
**Branch:** `fix/app-owned-run-paths-and-missing-mp3`

## Summary

Suno callbacks/polls can store `audio_id_ok` / `audio_id_alt` while leaving the
matching `audio_url_*` empty. Progress then under-counts `download_ready`, and
Download missing MP3s / redownload plans skipped those clips even though the
Suno CDN URL is deterministic (`https://cdn1.suno.ai/{id}.mp3`).

## Fix

- `cdn_url_for_suno_audio_id` / `coerce_suno_download_url`
- Callback + generate poll: synthesize CDN URL when clip has id but no URL
- `update_status`: empty-string no longer wipes existing URLs (`NULLIF` + `COALESCE`)
- Reconcile includes success rows with id but missing URL (not only both-null)
- `build_batch_redownload_plan` synthesizes + persists CDN URL from audio id

## Tests

- `pytest platform_api/tests/test_suno_audio_resolver.py -q`
- `pytest platform_api/tests/test_batch_service.py -k redownload -q`
