# Debug Session: suno-path-image-retry [OPEN]

## Summary
Investigate two runtime verification targets:
1. Updated Suno output path still appearing to resolve to old directory roots for unfinished work.
2. SLAI fallback image URL download retry/redownload behavior after previous hardening.

## Scope
- Collect runtime evidence only first.
- Do not modify business logic until evidence is gathered.
- Verify actual path resolution and retry behavior from logs.

## Hypotheses
1. Existing pending Suno rows still contain old persisted output directories that were not remapped because they did not match the old configured base root exactly.
2. The saved Suno path change is not triggering the remap path in the exact UI save flow Boss is using.
3. Runtime download/polling still prefers per-task stored outputDirOk/outputDirAlt values over the newly saved base directory during pending-task processing.
4. SLAI now prefers b64_json, but the provider is still returning URL fallback payloads in some cases, exercising the retry path.
5. SLAI fallback URL retry logic works, but failures still occur because the provider returns permanently invalid URLs rather than transient ones.
6. SLAI sometimes returns placeholder `b64_json` content (`data:text/plain...`) plus cache metadata (`cache_id`/`cache_expires_at`) before final image content is available, and the adapter currently stops too early.

## Evidence Plan
- Reproduce path-save and pending-task behavior.
- Capture runtime logs for Suno settings save, path remap decisions, and pending-task output directory resolution.
- Capture runtime logs for SLAI response mode, placeholder/cache retrieval attempts, and fallback download attempts.

## Current Evidence Update
- Earlier runtime log showed successful SLAI background generation followed by downstream Pillow failure: `Image job failed ... error=cannot identify image file <_io.BytesIO ...>`.
- Existing instrumentation confirmed provider response shape inspection happens before the failure path.
- Static verification in `python_app/services/image_provider_slai.py` showed `_extract_png_bytes_from_slai_response(raw)` accepted any base64-decodable payload without verifying that decoded bytes were an actual image.
- Boss provided new runtime evidence from the terminal:
  - `SLAI image generation returned no image bytes (expected b64_json; no usable fallback URL returned). Response preview: {"created":...,"data":[{"b64_json":"ZGF0YTp0ZXh0L3BsYWluOyBjaGFyc2V0PXV0Zi04O2Jhc2U2NCw=","cache_id":"...","cache_expires_at":...,"cache_ttl_seconds":...}]}`
  - The base64 decodes to `data:text/plain; charset=utf-8;base64,`, which is a placeholder text payload, not an image.
- Web evidence from Slai Beam docs indicates async jobs can require a retrieval/status call and may return final outputs/presigned URLs only after querying the task endpoint.
- Presence of `cache_id` and `cache_expires_at` in the initial response strongly supports the async cached-placeholder hypothesis.

## Confirmed Root Cause
SLAI has at least two non-final initial response modes for this adapter path:
1. `b64_json` may decode successfully but still not be a valid image.
2. `b64_json` may decode to a placeholder `data:text/plain...` marker while the real image is still behind provider-side async/cache retrieval identified by `cache_id`.

The adapter previously handled only direct bytes and direct URL fallback from the initial response. When the provider returned placeholder/cache metadata without a usable initial URL, the adapter raised an ordinary no-image error instead of retrieving the final result.

## Applied Fix
Updated `python_app/services/image_provider_slai.py` with the narrowest production-safe retrieval extension:
- Preserve behavior order:
  - return valid direct image bytes immediately
  - otherwise use direct URL from the initial response when present
  - otherwise detect placeholder/cache response pattern
  - then poll/retrieve the final result using existing auth/base-host style
  - if retrieval returns a URL, download it through the existing fallback downloader
- Added placeholder detection for:
  - decoded `b64_json` starting with `data:text/plain`
  - presence of `cache_id` / `task_id`
- Added bounded retrieval polling (4 attempts, small backoff) across narrow candidate endpoints derived from existing SLAI hosts:
  - `POST /beam/task` with `{"action":"retrieve","task_id":...}`
  - `GET /v1/images/generations/{id}`
  - `GET /v1/images/generations/{id}/status`
  - `GET /v1/images/generations/{id}/result`
- Reused existing Authorization/User-Agent request style from the adapter.
- Extended instrumentation minimally to log:
  - placeholder detected
  - retrieval attempts started
  - retrieval pending/no-final-result yet
  - retrieval returned final bytes
  - retrieval returned final URL
- Hardened fallback downloader slightly so a presigned ZIP-style output can still yield final image bytes if the provider returns an archive instead of a raw image.
- Added clearer error path distinguishing placeholder/cache retrieval failure from ordinary no-image responses.

## Next Verification Step
- Reproduce the same image-generation path that previously failed.
- In logs, confirm this sequence when the provider returns the placeholder form:
  1. `placeholder_detected`
  2. one or more `_retrieve_slai_cached_result` attempt logs
  3. either `bytes_ready` or `url_ready`
  4. if `url_ready`, a successful fallback download log
- Confirm the final image job completes without either of these previous failure modes:
  - `cannot identify image file <_io.BytesIO ...>`
  - `returned no image bytes ... no usable fallback URL returned`

## Status
OPEN
