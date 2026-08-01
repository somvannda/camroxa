# Changelog — Platform API

Backend REST/WebSocket API — generation, billing, streaming, image jobs, admin routes, public endpoints.

**Code:** `platform_api/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.9] - 2026-08-01

Deployed to sandbox and production (`release/desktop-1.0.9`, tag `v1.0.9`). Migration head
merge (`078`) plus `079_image_job_storage_key` applied to both — production had not yet
picked up `075_batch_channel_pipeline_complete` or any DistroKid migration, so its upgrade
ran the full `074 -> 075_distrokid_addon -> 076_distrokid_wav -> 077_batch_auto_distrokid ->
078 -> 079` chain (additive schema only; DistroKid's router/services remain unregistered).
See `docs/changelog/2026-08-01-v109-unified-branch-and-migration-merge.md`.

### Fixed

- Completed Progress pipelines no longer reopen when the local run folder is moved/archived; sticky `pipeline_complete` + overlay archive mode. See `docs/changelog/2026-07-28-freeze-completed-pipeline-when-folder-moved.md`.
- Secondary (Album 2) uniqueness: pool seed + AI polish with retries; never clear `alt_album` to Primary on failure; Progress/run-dir no longer copy Primary onto empty Secondary. See `docs/changelog/2026-07-28-progress-filters-and-album2-uniqueness.md`.
- Progress list: `limit` is row count after OK/ALT expansion; over-fetch batches; freeze Update timestamp when stage is Done/Error.
- Secondary album uniqueness hardening: never persist Primary + `II`/`Alt` as Album 2; export/image readiness no longer requires thumbnail for video start. See `docs/changelog/2026-07-28-secondary-album-no-ii-suffix.md` and `docs/changelog/2026-07-28-export-without-waiting-for-thumbnail.md`.
- `list_pending_suno_downloads` (background account-wide MP3 auto-sync) now excludes any channel whose `batch_channel_assets.pipeline_complete` is already `true` — previously it kept retrying every already-finished pipeline's failed/skipped download forever, on **every** machine the account logs into, which is what produced unrelated phantom date/profile folders (e.g. yesterday's batch, or an unrelated channel) on a fresh machine. Still-running pipelines (no `pipeline_complete` row yet, or explicitly `false`) keep auto-syncing to any device the account is logged into, by design — no per-device scoping yet. See `docs/changelog/2026-07-31-desktop-startup-freeze-hardening.md`.
- Migration `078_merge_pipeline_complete_and_distrokid` — sandbox's `alembic_version` had two independent, un-merged heads (`075_batch_channel_pipeline_complete` and the parked/unreleased `077_batch_auto_distrokid` from `feature/distrokid`), which breaks a bare `alembic upgrade head` deploy. This is a schema-no-op bookkeeping merge only; DistroKid's router stays unregistered in `main.py` and ships nothing new. See `docs/changelog/2026-08-01-migration-heads-merge.md`.

### Added

- `image_jobs.storage_key` (migration `079_image_job_storage_key`, after a `078` merge revision reconciling this lineage with the parked, unreleased DistroKid migrations — see Fixed) — background/thumbnail image job outputs are now durably archived to Backblaze in the background on every successful generation (mirrors the existing MP3 streaming-archive pattern), instead of only living in the API server's local disk cache. `GET /api/v1/image-jobs/{job_id}/output` now falls back to the Backblaze copy (and repopulates the local cache) if the local cache and any client-reachable path are both missing, so a lost server cache no longer means paying the AI provider again to regenerate a previous batch's images. See `docs/changelog/2026-07-31-desktop-startup-freeze-hardening.md` (v1.0.9 part 4).
- `POST /music/downloads/batch-redownload-plan` — batch/channel-scoped Suno audio re-download plan (ignores `downloaded_ok`/`downloaded_alt`), powering the desktop "Change Run Folder & Resume" recovery flow. `download_url` is the original Suno URL (primary — Suno retains audio 14 days); a new optional `fallback_download_url` carries a signed Backblaze URL (`stream_tracks.storage_key`, archived automatically on every successful Suno callback) for the desktop client to retry with only if the Suno URL is dead — Backblaze is never hit proactively. See `docs/changelog/2026-07-31-desktop-startup-freeze-hardening.md` (v1.0.9 update).

## [Unreleased]

### Fixed

- Startup `alembic upgrade heads` now serializes across worker processes via a Postgres advisory lock — with `API_WORKERS` > 1, every worker previously ran migrations independently and concurrently, which raced DDL against other workers' open connection pools and caused a ~30 minute burst of 500s across nearly every endpoint after today's v1.0.9 production deploy. See `docs/changelog/2026-08-01-migration-worker-race-incident.md`.
- Production/sandbox systemd unit templates now set `PYTHONUNBUFFERED=1` — stdout was block-buffered, so error tracebacks (including this incident's) were invisible in `journalctl` until a restart. Same incident doc.

- Admin POST /api/v1/users/{user_id}/set-password — set password + revoke sessions (same complexity rules as self-service). See docs/changelog/2026-07-27-admin-set-user-password.md
- Streaming play counts: `stream_tracks.play_count` (migration `072`); increment on public `play-url`; album lists expose sum as `play_count`
- Public streaming list pagination: `GET /public/streaming/albums|artists|search` return `{ items, total, limit, offset }`; search accepts `offset`
- Admin streaming catalog pagination: `GET /admin/streaming/catalog` and `.../catalog/albums` return `{ items, total, limit, offset }` with `offset`, `q`, `publish_status`
- Public `play-url` includes `album_id`, `user_id`, `lyrics` for music portal Now Playing rail
- Streaming library likes: migration `073_stream_track_likes`; `GET/PUT/DELETE /streaming/library/likes`
- Suno timestamped lyrics → LRC on stream upload/metadata sync (`074_suno_audio_ids`; `get-timestamped-lyrics`)
- Migration `075_batch_channel_pipeline_complete` — sticky desktop pipeline completion on channel assets

### Changed

- `/auth/logout` accepts cookie auth (not Bearer-only) for music portal same-origin sessions

### Changed

- Production HTTPS live (`api`/`camxora.com`/`www`/`app`/`admin`/`music`); Resend SMTP configured on prod API env. See `docs/changelog/2026-07-26-production-tls.md` and `docs/changelog/2026-07-26-production-smtp.md`.
- Production admin seeded; local plans (13) imported. See `docs/changelog/2026-07-26-production-admin-and-plans.md`.
- Sandbox scrubbed system/catalog config imported to prod. See `docs/changelog/2026-07-26-sandbox-config-to-production.md`.
- Streaming catalog + prod B2 bucket wired. See `docs/changelog/2026-07-26-production-streaming-catalog.md`.
- Sandbox AI API keys re-encrypted onto prod. See `docs/changelog/2026-07-26-production-api-keys.md`.
- CutLuy live secret + webhook secret on prod. See `docs/changelog/2026-07-26-production-cutluy.md`.

### Fixed

- Desktop installer publish: accept `CamxoraSetup-*.exe` / `Camxora-Setup-*.exe` in version filename parse; optional `version` on publish body. See `docs/changelog/2026-07-26-software-update-setup-filename.md`.

## [2026-07-25]

### Added

- **`POST /batches/{id}/rewrite-album`** and **`POST /batches/{id}/songs/{id}/rewrite-title`:** regenerate Primary/Secondary album or one song title (bills album/title draft slot; keeps lyrics/status).
- **Music Moods:** migration `069` + 22 seeded system moods; CRUD mirrors Structures (`/prompts/moods`, `/me/moods`, workspace/public); batch `mood_id` + `shuffle_mood`; history `mood_name`.
- **`DELETE /batches/{batch_id}`:** users can hard-delete batches with no successful/pending Suno audio (`pending` / `draft_failed` / `draft_ready` / `suno_failed` only); restores leftover draft-meter slots for `draft_failed` songs; does not re-credit wallet or gift song quota.

### Fixed

- **Music History date filter:** `from_date` / `to_date` use strict planned-run window overlap or created day; ignore `updated_at` so retries do not reopen old batches
- **Title/album garbage gate:** reject mixed-script and glued word-salad metadata (e.g. CJK/Cyrillic junk, `obligations:bold`, `streetconnections`); Suno submit also refuses invalid titles. Draft forced title/album are validated the same way.
- **Title/album rewrite LLM empty response:** rewrite uses the text fallback chain and skips empty provider responses instead of hard-failing with “unexpected response shape”.
- **Album image job race (`BG 2/2`):** concurrent Suno completions could insert two backgrounds and two thumbnails per channel. Unique index + conflict-safe insert keep one BG and one TH per channel; migration `070` dedupes existing rows.

### Fixed

- **Draft fail meter under-refund:** split lyric/title/album billing now refunds all billed draft slots (was often `count=1` after 2–3 slot deducts).
- **DeepSeek V4 + text fallback:** retired `deepseek-chat` no longer hard-stops draft generation; text chain tries sibling models within a provider, then advances to SLAI/OpenAI even on permanent 400s.
- **Local pricing edit 422:** `external_cost_cents` of `0` (local video/manual/merge COGS) is accepted on create/update instead of requiring ≥0.0001 credits.

### Changed

- **Suno style length:** raised from 255 → **1000** chars (V5/V5_5 customMode limit); migration `071_suno_style_1000` expands `suno_tasks.style`
- **Lyric rewrite quality gate:** polish trims corrupt tails before LLM, caps output, rejects word-salad; aligned with mood+title+structure (not description).
- **Lyric rewrite = draft lyric context:** polish / auto-rewrite / recover use **mood + title + structure** (not song description). `POST /generation/polish-lyrics` accepts `mood` / `mood_id` / `structure_id` and resolves catalog content from linked songs.
- **Draft pipeline:** album → title → lyric; album/title/lyric use **mood** (+ pools/structure); lyric prompts exclude song description; Suno style stays description-only. Lyric temperature capped vs prior `creativity/100*1.5`.
- DeepSeek defaults/registry: `deepseek-v4-flash` / `deepseek-v4-pro` (legacy aliases `deepseek-chat` / `deepseek-reasoner`); thinking disabled for reliable `content`.
- SLAI seed cost tiers: mimo `~$0.0001414/1K`, sol `~$0.0001033/1K`, terra `~$0.0000582/1K`, luna `~$0.0000307/1K`; image `slai/gpt-image-2` `~$0.0067/img` (150 images / $1).

### Added

- Background **image job auto-retry**: transient provider failures re-queue as `pending` up to `image_job_max_attempts` (default 3); fail-budget / quota / insufficient credits stay terminal.
- `GET /music/history`: optional `from_date` / `to_date` query filters; limit raised to **100** (default 25).
- Parse history `from_date`/`to_date` to `datetime.date` before asyncpg binds (fixes 500 `'str' object has no attribute 'toordinal'`).
- **Suno reject auto-recovery:** content-policy/`REJECTED` failures rewrite lyrics via lyric LLM then resubmit (max 2 auto attempts).

### Fixed

- Dashboard weekly `usage_by_day` window now includes **today** (`today-6..today`); previously ended at yesterday and hid same-day Manual exports.

### Added

- `video_manual` local consume/refund (same price/quota pool as `video`, separate usage key).
- Dashboard stats: `studio_exports`, `manual_exports`, `youtube_uploads`; daily usage breakdown fields.
- Quota status already exposed `daily_videos_*` / `daily_merges_*` (now surfaced in portal UI).

### Changed

- `videos_generated` alias = studio + manual track exports; `videos_uploaded` remains YouTube successes.

## [2026-07-19]

### Added

- `GET /api/v1/public/desktop-release` — public published desktop release (version, download URL, release notes) for website download page.
- Suno blocklist follow-ups: per-channel scope, sanitize metadata on songs, failure metrics admin endpoint, guarded auto-retry on callback.
- Migration `067_song_suno_sanitize_metadata`.

### Changed

- Public blog list supports optional `category` query param (case-insensitive) for website `/changelog`.

## [2026-07-18]

### Added

- Suno lyrics sanitization service, `POST /generation/lyrics-suno-check`, blocklist CRUD admin APIs, migration `066_suno_blocklist_terms`.
- AI routing real stored costs in provider list API.

## [2026-07-17]

### Added

- Daily quota bank and credit-bypass billing controls.
- Streaming genre browse public API and catalog metadata sync.
