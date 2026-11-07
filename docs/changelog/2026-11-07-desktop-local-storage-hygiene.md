# Desktop local storage hygiene (audio cache, logs, update leftovers)

**Date:** 2026-11-07
**Surface:** `camxora_python` (desktop)
**Branch:** `desktop/cache-hygiene`

## What

A user machine had **25.4 GB** in `%LOCALAPPDATA%\Camxora\cache\audio-analysis`
(604 entry pairs, ~42 MB each). The cache wrote entries but never deleted any,
so every export at a different fps/point count, every re-downloaded track, and
every old `CACHE_VERSION` left another tens-of-megabytes file behind.

| Place | Change |
|---|---|
| `shared/services/audio_analysis_cache.py` | `CACHE_VERSION` 3 → 4. `mag` stored as **float16**; `freqs` / `bass_idx` / `mid_idx` / `treble_idx` are no longer persisted (rebuilt on load). Atomic `.part` + `os.replace` writes. New `prune_audio_analysis_cache()`, `audio_analysis_cache_stats()`, `clear_audio_analysis_cache()`. |
| `visualizer/audio.py` | `AudioAnalyzer.from_cached_arrays()` derives frequency bins and band indices from `sample_rate + n_fft` instead of accepting them. |
| `app/bootstrap.py` | `_start_local_storage_maintenance()` daemon thread prunes the audio cache and stale update artifacts on startup. |
| `shared/services/app_logger.py` | `_prune_old_files()` now also ages out and rotates the non-`camxora-*.log` diagnostics (`audio-load-diag.log` was 16 MB and unbounded). |
| `shared/services/software_update_installer.py` | Apply scripts call `Remove-CamxoraPackage` after a successful exe/msi install; `cleanup_stale_update_packages()` removes installers/staging older than 24 h (a 417 MB `CamxoraSetup-update.exe` was left behind). |
| `features/settings/views/settings_view.py` | New **Storage** panel (Preferences): shows cache size/entries/limit and offers "Clear audio cache". |

## Eviction policy

- Broken pairs (`.npz` without `.meta.json` and vice versa) are deleted.
- Entries whose meta `version` is not `CACHE_VERSION` are deleted.
- Entries unused for **30 days** are deleted.
- Remaining entries are LRU-trimmed to a **2 GB** budget.
  Override with `CAMXORA_AUDIO_CACHE_MAX_MB` (minimum 256 MB).
- Cache hits `os.utime()` the pair so LRU stays accurate on Windows, where
  last-access timestamps are often disabled.
- Runs on a daemon thread at startup, and after writes (throttled to once per
  10 minutes) so it never blocks preview or export.

## Expected size effect

- float16 + dropped derived arrays: roughly **40–55 % smaller** per entry
  (~42 MB → ~18–25 MB for a typical track).
- The directory is now bounded by the 2 GB budget instead of growing forever.
- The existing 25 GB is all v3, so the first prune removes it wholesale.

## Tests

```bash
cd camxora_python
python -m pytest tests/test_audio_analysis_cache.py tests/test_app_logger.py \
    tests/test_software_update_installer.py tests/test_settings_view.py -q
```

Added coverage: float16/derived-array layout, stale-version + orphan pruning,
size-budget trimming, retention cutoff, and full clear.

## Follow-ups

- `tests/test_application.py::test_router_navigates_all_routes` fails on `main`
  because `app/router.py` imports `features.logs.views.log_view`, which is not
  in the repo. Unrelated to this change; needs its own fix or route removal.
- Consider keying the cache by content hash so a moved/re-downloaded track
  reuses its entry instead of creating a new one.
