# Changelog — Platform API

Backend REST/WebSocket API — generation, billing, streaming, image jobs, admin routes, public endpoints.

**Code:** `platform_api/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

### Changed

### Fixed

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
