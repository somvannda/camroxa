# Changelog — Platform API

Backend REST/WebSocket API — generation, billing, streaming, image jobs, admin routes, public endpoints.

**Code:** `platform_api/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2026-08-05] — Desktop 1.1.1 image modes (production)

### Added

- Image **prompt-only** source modes (P0): prefs `imageBackgroundSourceMode` / `imageThumbnailSourceMode` (`prompt_only` | `category` | `personal_reference`). API skips sample/style references for prompt-only BG/TH; thumbnail composite no longer requires a style sample; User reference returns a clear not-ready error until P2. See `docs/changelog/2026-08-05-image-prompt-only-p0.md`.
- `POST /image-jobs/retry` with `force=true` resets successful image jobs for regenerate. See `docs/changelog/2026-08-05-image-prefs-ux-and-force-regen.md`.
- `POST /image-jobs/manual-generate`: today-dated **Not available** batch (`status=manual_image`, `song_count=0`) + BG/TH jobs; runs the clicked kind with normal image-job billing. Migration `082`. See `docs/changelog/2026-08-05-manual-gen-queue-row.md`.
- Pairs with desktop installer **1.1.1** (`CamxoraSetup-1.1.1.exe`). After deploy, **restart image workers** so they load the new code. See `docs/changelog/2026-08-05-desktop-1.1.1-image-prompt-modes.md`.

## [Unreleased]

### Changed

- Cutover: JSON media URLs, Suno callbacks, YouTube OAuth, desktop-release links, geo/auth, and nginx stream/WS are `/api/v3` only. See `docs/changelog/2026-08-26-api-v3-cutover-emitted-urls.md`.
- `/api/v3` is the full canonical API surface (dual-mount of former v1 routers + CutLuy billing + webhooks + wallet). `/api/v1` and `/api/v2` remain temporary. See `docs/changelog/2026-08-25-api-v3-superset-dual-mount.md`.
- Sandbox credits-only billing cutover: plan grants locked (incl. hidden $79 → 3000 monthly credits), leftover mint idempotent, `credits_only_v3_charge` On. See `docs/changelog/2026-08-25-sandbox-billing-cutover-v3.md`.
- Fix Free daily mint (`daily_grant` lot tag) and streaming likes wiring that caused music web `/me/credits`, `/web-music/quota`, and `/streaming/library/likes/ids` 500s. See `docs/changelog/2026-08-25-fix-v3-daily-grant-and-likes.md`.
- `GET /api/v3/subscriptions/plans` includes `daily_credits` from DB (was always `0` for Free). Same incomplete-payload class as admin credits-only.
- Admin user-spend uses the unified plan resolver only (no separate Music-tag web-sub path). Sandbox 500 fixed. See `docs/changelog/2026-08-23-wallet-api-audit-e2e.md`.
- Admin user list/detail resolve Plan from license then CutLuy web sub. License list includes web subscriptions. User-spent plan filter matches that resolver. See `docs/changelog/2026-08-23-admin-users-licenses-wallet.md`.
- CutLuy plan fulfill / renew and top-up write the shared wallet (period grant + pack lot). Web leftover conversion is a separate one-shot. Generate and web chrome no longer spend or add v2 remaining. See `docs/changelog/2026-08-23-one-wallet-web-ledger.md`.
- `GET /api/v3/me/credits` mints the Free daily grant so web chrome can show the shared wallet after login. See `docs/changelog/2026-08-23-web-credits-v3-balance.md`.
- Admin usage/finance summaries count v3 period/daily grants and group `v3_music` with music. See `docs/changelog/2026-08-23-admin-v3-plans-and-reports.md`.
- When `credits_only_v3_charge` is On, Web Create uses the same charge model as desktop: plan amounts, no Pro skip, lyrics = `lyric`, Free daily via a v3 lot. CutLuy / `web_subscriptions` still debit v2 for the quoted amount. See `docs/changelog/2026-08-23-web-create-v3-charge.md`.
- Desktop login/refresh with `X-Camxora-Client: desktop` and desktop generate doors require a paid plan. Free accounts get `403 DESKTOP_PLAN_REQUIRED`. See `docs/changelog/2026-08-23-desktop-paid-gate-and-website-pricing.md`.
- Public profile-addon quotes require `is_public`. Addon slots no longer scale monthly song meters. See `docs/changelog/2026-08-22-credits-only-public-cards-and-addon-skus.md`.
- Web Music free daily limit reads the **Free** plan `daily_credits` first. Sandbox deleted `web_music_free_daily_credits`. See `docs/changelog/2026-08-23-credits-only-sandbox-cutover.md`.
- Sandbox Credits-page music price is **10** (was 7.5). `credits_only_v3_charge` is **On** on sandbox only after leftover mint + period grant on a dedicated test license.

### Added

- Credits-only **`/api/v3`** billing (quote/charge/refund, public plans that honor
  `is_public`, leftover conversion dry-run). Uses the same Admin Credits/Plans
  wallet tables as v1. Existing `/api/v1` generate and `/plans/public` are
  unchanged. See `docs/changelog/2026-08-22-credits-only-api-v3.md`.
- Flagged Generate debit via v3 (`credits_only_v3_charge`, default off). When on,
  music/draft/image/video/merge charge the shared wallet and skip quota-first.
  See `docs/changelog/2026-08-22-credits-only-admin-plans-and-generate-flag.md`.
- `GET /api/v1/plans/public` requires `is_active AND is_public`. Hidden $79 /
  channel rows no longer leak onto the website. See
  `docs/changelog/2026-08-22-v1-plans-public-is-public.md`.

### Fixed

- Create play Ready with Chrome “no supported source”: concurrent packaging
  left `content_key_id` pointing at an older key than the CXA1 file. Lock +
  skip-if-ready, then repair DB keys from the package header. See
  `docs/changelog/2026-08-25-web-music-play-key-mismatch.md`.
- Library likes 500: `StreamingCatalogService` now accepts the `redis=`
  kwarg `wire_dependencies` already passes. API restart after the ingest
  hotfix loaded the mismatch. See `docs/changelog/2026-08-25-web-music-finishing-b2-ingest.md`.
- Web Create SUCCESS now starts Backblaze ingest. The Suno callback had skipped
  `web_music`, so clips could stay on Finishing forever. Create poll retries
  unready SUCCESS clips. See `docs/changelog/2026-08-25-web-music-finishing-b2-ingest.md`.
- v3 wallet / period-grant SQL no longer selects ambiguous `id` when joining
  `plans` to `licenses`. Sandbox `credit_wallet_lots` / `billing_conversion_runs`
  are owned by the API role.

### Security

- Artist royalty stream accounting: server-validated heartbeats, self-play exclusion, fraud scoring, and catalog geo parity for `/public/streaming`. See `docs/changelog/2026-08-20-artist-royalty-program.md`.
- Protected catalog/Create playback: AES-256-GCM packages, License API sessions, owner-only watermarked downloads, and no Suno/B2 origin URLs in the browser. Unconfirmed users cannot play or export. Theft-vector suite (`test_protected_playback_theft_vectors.py`) covers 1000+ Range-stitch and save-as cases. Production leftover encrypt now also seals the original MP3 object and owner WAV/LRC sidecars (SRT is derived from LRC). See `docs/changelog/2026-08-20-protected-playback.md`.
- Admin blog CRUD (`/api/v1/admin/blog-posts`) now requires `Depends(require_admin)`.
  Unauthenticated list/create/update/delete previously skipped auth. See
  `docs/changelog/2026-08-19-admin-blog-require-admin.md`.
- Unconfirmed accounts can only call session/profile routing endpoints until they
  verify email. Other authenticated routes return 403. See
  `docs/changelog/2026-08-17-email-confirm-gate.md`.
- Music web is Cambodia-only (`CF-IPCountry=KH`; Tor/unknown/missing country blocked). Attack-like generate/auth patterns freeze Create for 6 hours (admin can set 1/6/24/72h). Signup farm caps stay 3/hour and 5/day; freeze is extra. See `docs/changelog/2026-08-18-music-web-geo-gen-freeze.md`.
- Music Web free-credit farm protection: required Turnstile on web register, per-IP signup caps, and a shared 5-song/day network cap. Public music signup stays open. See `docs/changelog/2026-08-18-music-web-signup-farm-protection.md`.

### Added

- AES-128 HLS lane for iOS Safari: ffmpeg packaging at ingest, session-bound `index.m3u8` + key routes, admin HLS backfill. See `docs/changelog/2026-08-21-ios-hls-aes128-playback.md`.
- `GET /api/v1/web-music/licenses/play/{token}` — session-bound clamped MP3 stream (server-side CXA1 decrypt, 90s cache) for iOS native HTML audio playback. See `docs/changelog/2026-08-21-ios-native-html-playback.md`.
- `GET /api/v1/web-music/playlists/memberships` — owner clip-to-playlist map for Create-page chips. Packaged clips can be added to playlists (ready check matches playback). See `docs/changelog/2026-08-21-playlist-add-packaged-ux.md`.
- Music web play traces: `POST /api/v1/web-music/licenses/client-trace` logs `music_web_play_trace` and stores `playback_events.detail` (migration `114`). See `docs/changelog/2026-08-21-ios-safari-play-trace.md`.
- Overview (`/api/v1/web-music/studio/*`) owner APIs, versioned royalty policy, settle worker, and admin payout/fraud/origin endpoints. Studio tracks are per version (ok/alt), with public = on a public playlist or published catalog. See `docs/changelog/2026-08-20-artist-royalty-program.md`.
- Opt-in artist pages (`/api/v1/web-music/artist-pages`, public list/detail). Multi-page schema with admin `artist_page_limit` (default 1). Create/publish require name, location, country, and at least one genre. Cover crop, contact email, and Facebook/TikTok/Instagram/YouTube links are optional. Typed genres (up to 10) from an expanded music catalog including Khmer/SEA labels. Owners can attach tracks and playlists to a page. See `docs/changelog/2026-08-20-artist-pages.md` and `docs/changelog/2026-08-20-artist-page-attach.md`.
- Telegram ops feed posts signup, login, paid checkout, credit spend, plan-quota
  use, and refunds to a group chat. `/stats` and `/burncredit` reply in-chat;
  burn tables also post at 10:00 PM Asia/Phnom_Penh. See
  `docs/changelog/2026-08-18-telegram-ops-activity-feed.md`.
- Admin user detail lists Camxora Music generations with prompt/settings and
  authenticated MP3 playback. See
  `docs/changelog/2026-08-19-admin-user-generated-songs.md`.

### Changed

- Admin Users keeps live avatar/freeze fields and infers Music **Free** daily
  credits on the list (sandbox table sync). See
  `docs/changelog/2026-08-19-sandbox-admin-users-table-sync.md`.
- Admin Users infers Music **Free** (50 daily credits) for `music_web` users
  without a paid `web_subscriptions` row. Credits show today's used / limit;
  Burned is lifetime `web_music_daily_usage` so midnight reset does not wipe
  the column. Studio debit sums use absolute micro-units. See
  `docs/changelog/2026-08-19-admin-users-lifetime-burn.md` and
  `docs/changelog/2026-08-18-admin-music-free-daily-display.md`.
- Admin `GET /users` includes Camxora Music plan + remaining/limit/burned credits
  from `web_subscriptions` (desktop licenses alone showed "No plan" / leftover
  studio wallet). See `docs/changelog/2026-08-18-admin-users-music-credits.md`.
- Admin `GET /users` includes `products` (Music / Studio tags) from `users.products`.
  See `docs/changelog/2026-08-18-admin-users-product-tag.md`.
- Startup Alembic runner skips leftover sibling heads (retired `084_*` files) and time-boxes upgrades so a hung migration cannot leave the catalog on `Database pool not initialized`. See `docs/changelog/2026-08-17-alembic-skip-leftover-heads.md`.

### Fixed

- Packaged web-music clips can be added to playlists (`add_playlist_item` uses the playback ready check, not origin URLs). See `docs/changelog/2026-08-21-playlist-add-packaged-ux.md`.
- `GET /v2/credits/balance` no longer 500s when a paid subscription is missing `last_credit_reset`. See `docs/changelog/2026-08-20-artist-pages.md`.
- Stream play no longer one-shots a full MP3: `Range: bytes=0-` (and missing Range) is clamped to 256 KiB 206, and the proxy truncates origin bodies that ignore Range. See `docs/changelog/2026-08-19-web-music-stream-range-cap.md`.
- Music-web play no longer kicks a logged-in session to login: geo gate is pure ASGI (does not wrap Range audio), `/stream/ok` and `/stream/alt` are trusted play URLs, and unconfirmed users can still listen. See `docs/changelog/2026-08-18-music-web-geo-gen-freeze.md`.
- Settings ignore unknown `PLATFORM_*` env vars (Telegram ops keys on production must not crash boot). Audio proxy keeps `is_missing_range` for production stream routers.
- `GET /v2/subscriptions/my-subscription` still returns an active web-music subscription when the plan row is missing (LEFT JOIN). Credit balance includes `current_period_end` for the profile next-billing date. See `docs/changelog/2026-08-18-music-web-profile-current-plan.md`.
- Web Music Create: validate title and admin Suno blocklist **before** charging; reject blocked lyrics instead of submitting them; allow Khmer titles; refund if Suno later rejects. See `docs/changelog/2026-08-18-web-music-blocklist-precheck.md`.
- Create workspace `clips[].ready` waits until origin audio actually serves bytes (or B2 has our file). Suno SUCCESS+URL alone is not enough. See `docs/changelog/2026-08-18-music-web-stream-ready.md`.
- Web-music WAV download no longer runs WAV bytes through the MP3-only Suno downloader (RIFF was rejected). WAV URLs mislabelled as `audio/mp4` are accepted; a previous failed conversion is retried; unexpected errors return a retryable 422 instead of a blank 500. Owner play URLs `/stream/ok` and `/stream/alt` are routed again (query-param stream still works). Clip titles can be renamed per Version via `title_ok` / `title_alt`. See `docs/changelog/2026-08-18-music-web-workspace-follow-playing.md`.
- Login no longer 500s on invalid credentials or lockout: import `AccountLockedError` in the auth router. See `docs/changelog/2026-08-17-sandbox-login-alembic-hang.md`.
- Web music lyric/style assist: accept full 5000-character lyrics on `generate-styles`, and return a clear retryable 502 when the text LLM is down. See `docs/changelog/2026-08-17-music-web-generate-assist.md`.
- Create playback: return stored vocal/slider settings and clip durations; proxy play through the API with HTTP Range (do not 302 to Suno/B2). See `docs/changelog/2026-08-17-music-web-create-playback.md`.
- Catalog play-url no longer returns a signed B2 URL; `/public/streaming/tracks/{id}/stream` proxies Range audio the same way. See `docs/changelog/2026-08-17-catalog-playback-proxy.md`.
- Public streaming catalog JSON omits origin audio fields (`storage_key`, `suno_audio_id`). See `docs/changelog/2026-08-17-music-web-no-origin-audio-urls.md`.
- Startup Alembic runner skips leftover sibling heads and time-boxes upgrade so sandbox cannot hang on broken merge stubs.

### Changed

- Web-music Simple `prompt` max is **5000** (Suno V5 custom lyrics); empty Simple style falls back to the description (1000-char style cap). See `docs/changelog/2026-08-18-web-music-simple-prompt-suno-limits.md`.
- Web-music generation clips include `duration_seconds` from stored Suno durations (`104_suno_task_durations`). See `docs/changelog/2026-08-17-web-music-clip-duration.md`.
- Unconfirmed users cannot call authenticated product APIs (including web-music generate) until they verify email. See `docs/changelog/2026-08-17-music-web-email-confirm-lock.md`.
- Web-music checkout/top-up fulfill only the bound CutLuy payment, allowlist return/checkout URLs, and rate-limit purchase + status poll. See `docs/changelog/2026-08-17-music-web-checkout-security.md`.
- Web-music CutLuy payments no longer attach the portal `payment_link_id`. Status poll endpoints fulfill subscription and top-up credits if the webhook has not already run. See `docs/changelog/2026-08-17-music-web-owned-checkout.md`.

### Added

- `suno_tasks.stream_ready_ok` / `stream_ready_alt` (migration `106`) so Create Ready means the file actually streams. See `docs/changelog/2026-08-18-music-web-stream-ready.md`.
- `PATCH /api/v1/web-music/generations/{id}` updates a Create-workspace song title. See `docs/changelog/2026-08-18-music-web-workspace-follow-playing.md`.
- Web music public discovery endpoints: `/web-music/public/playlists`, `/web-music/public/artists`, `/web-music/public/artists/{user_id}`. See `docs/changelog/2026-08-17-web-music-explore-public-playlists.md`.
- Public recent tracks endpoint `/web-music/public/tracks/recent` and public playlist streaming access for explore playback.

### Changed

- `get_user_subscription` returns only active paid subscriptions (fixes pending checkout showing as Starter on profile).
- User profile photo upload and avatar media route; web music generation likes for player heart button.
- Streaming public artist list includes `avatar_url` for uploaded profile photos. See `docs/changelog/2026-08-17-streaming-artist-list-avatars.md`.
- Web music download hardening: MP3-only Suno fetch, play tokens, download rate limits, B2 backfill on fallback. See `docs/changelog/2026-08-17-web-music-download-hardening.md`.
- Web music LRC cached on Backblaze (`101_web_music_b2_lrc_storage`); playback and streaming play-url require login (free users can play). See `docs/changelog/2026-08-17-web-music-lrc-b2-login-playback.md`.
- Web music credit hardening (P0): async Suno failure refunds, subscription period enforcement, 15-min maintenance loop, removed public `/v2/credits/consume`. See `docs/changelog/2026-08-17-web-music-credit-hardening-p0.md`.
- Web music credit hardening (P1): refund to monthly/top-up pools from debit metadata, reservation→task debit linking, refund idempotency index, removed v2 `credit_wallets` updates. See `docs/changelog/2026-08-17-web-music-credit-hardening-p1.md`.
- Web music credit billing polish: simple-mode Suno lyrics included in song charge (credits reserved first); yearly plans refresh monthly credits every 30 days. See `docs/changelog/2026-08-17-web-music-credit-billing-polish.md`.

See `docs/changelog/2026-08-17-music-web-profile-likes-avatar.md`.

### Changed

See `docs/changelog/2026-08-17-web-music-lrc-srt-pro-gate.md`.

### Added

- `PATCH /api/v1/web-music/workspaces/{workspace_id}` to rename a user's workspace.

See `docs/changelog/2026-08-17-web-music-workspace-rename.md`.

### Added

- Web music playlists API and migration `096_web_music_playlists`.

See `docs/changelog/2026-08-17-music-web-downloads-playlists-cutluy.md`.

### Changed

- Web music generation clips expose Suno cover URLs; advanced create settings persist on `suno_tasks`; timed lyrics download (LRC/SRT) via Suno alignments; migration `098_web_music_suno_cover_urls`.

See `docs/changelog/2026-08-17-web-music-workspace-track-ui.md`.

- Web music downloads require paid subscription (free users can still stream/play).
- CutLuy v2 subscription/top-up checkout uses `/v1/payments` with admin DB credentials (KHQR checkout URL).

See `docs/changelog/2026-08-17-music-web-downloads-playlists-cutluy.md`.

- Web music billing is fully credit-based: free users get 50 daily credits (5 songs), subscribers use monthly + top-up pools.

See `docs/changelog/2026-08-17-web-music-unified-daily-credits.md`.

- Web music style AI prompt expands user Styles field into Suno-ready production text.

See `docs/changelog/2026-08-17-web-music-style-prompt-enhancement.md`.

- Auto-generate lyrics draft prompt limit raised to **5000** characters (was 500).

See `docs/changelog/2026-08-17-web-music-lyrics-prompt-5000-char-counts.md`.

### Added

- `web_music_lyrics` credit-priced operation; migration `094_web_music_lyrics_pricing` fixes style pricing units.

See `docs/changelog/2026-08-17-web-music-section-errors-lyrics-billing.md`.

- Web music workspaces API and migration `092_web_music_workspaces`.

See `docs/changelog/2026-08-17-web-music-create-ui-workspaces.md`.

- Web music v2 subscriptions/top-ups: CutLuy checkout, webhook routing, credit balance API.
- Email verification page (`/verify-email`) with resend; register redirects after signup.
- Shared compact auth form shell for login/register.
- Admin `/plans` web music section: manage music subscriptions and top-up packs separately from desktop.

See `docs/changelog/2026-08-16-admin-web-music-plans.md`.

### Fixed

- CutLuy credentials load from `PLATFORM_CUTLUY_*` settings; v2 DB adapter and plan queries use `monthly_song_limit`.
- Subscription plans API parses JSONB `features` correctly.
- Register no longer 500s when Turnstile token is omitted: removed inner `get_settings` import that shadowed module scope.

### Added

- Automatic Backblaze B2 upload for web music MP3s and WAVs (permanent storage)
- Migration `087_web_music_b2_storage` adds B2 storage keys for both MP3 and WAV files
- Web music download/stream endpoints now serve from Backblaze when available, fall back to Suno CDN
- WAV downloads are now free (no credit cost) and permanently stored
- Simplified storage structure for web music: `web-music/{user_id}/{song_slug}-{variant}.{mp3|wav}`
- See `docs/changelog/2026-08-16-web-music-backblaze-auto-upload.md`

- Music-web product tag (`users.products`) and `/api/v1/web-music` generate /
  list / status / MP3 download. Auth-only (no desktop license or channel
  profile); **5 free songs** then Upgrade to Pro (`web_music_free_daily_limit`,
  default 5, lifetime). Create polls sunoapi.org record-info if the callback
  is slow. See `docs/changelog/2026-08-15-music-web-suno-create.md`.
- Music-web Suno advanced options: V5/V5.5 model selector, negative tags, vocal
  gender, style weight, weirdness constraint, audio weight. Added
  `POST /api/v1/web-music/generate-draft` for auto-generating lyrics and title.
- Music-web WAV downloads: `/api/v1/web-music/generations/{id}/download-wav`
  with on-demand Suno WAV conversion. Tracks WAV task IDs and URLs in
  `suno_tasks` (migration `085`). Polls Suno for conversion status (up to 3
  attempts). See `docs/changelog/2026-08-16-music-web-wav-downloads.md`.
  See `docs/changelog/2026-08-15-music-web-suno-advanced-options.md`.
- Music-web security hardening: IP-based abuse detection, rate limiting on all
  endpoints, strict input validation, atomic quota enforcement, comprehensive
  logging. Prevents account cycling, quota bypass, and API key theft.
  See `docs/changelog/2026-08-15-music-web-security-hardening.md`.
- Music-web geo-restrictions & daily limits: Changed to 5 songs **per day**
  (was lifetime), added per-IP daily limits (5/day), Cambodia-only access,
  VPN/proxy blocking. Enforces daily reset, prevents multi-account abuse.
  See `docs/changelog/2026-08-15-music-web-geo-vpn-daily-limits.md`.


### Fixed

- Production admin user-detail 500 for studio accounts with channel profiles: `upload_path_exists` was used after the import was replaced by avatar helpers. See `docs/changelog/2026-08-18-admin-user-details-upload-path-import.md`.
- Desktop Progress no longer stays on **Image / background still in progress**
  after image jobs succeed. Generation-complete (job success) is separate from
  export-ready (local PNG). `long_ready` is not faked from Windows paths the
  API host cannot open, so desktop export/automation is unchanged. See
  `docs/changelog/2026-08-16-progress-trust-image-job-success.md`.
- Admin period quota top-ups (image/song/draft/etc.) are now honored by
  subscription coverage. Previously the admin UI showed remaining allowance
  but generation still demanded wallet credits. See
  `docs/changelog/2026-08-16-image-topup-plan-cover.md`.

- Admin User Spent Song chip (`S`) was always 0% because usage is stored as
  `music` and the page reads `song`. Also fold `video_manual` into the Video
  meter. See `docs/changelog/2026-08-16-user-spent-song-meter.md`.

- Pipeline Ops no longer treats leftover streaming-archive 403s (expired
  `cdn1.suno.ai` MP3 URLs) as a live pipeline Error. Those stay on the
  streaming chip; music+image complete rows promote to Done. Desktop Progress
  sync no longer bumps `batches.updated_at` when status is unchanged. See
  `docs/changelog/2026-08-16-pipeline-stale-streaming-error.md`.

- Suno CDN `{id}.m4a` (Opus-in-MP4) URLs are rewritten to `{id}.mp3` before
  persist / pending download / streaming fetch. Non-MPEG bodies are not stored
  as MP3. See `docs/changelog/2026-08-15-suno-prefer-real-mp3.md`.
- Opening Software Updates clears a leftover draft when its installer file is
  gone (e.g. 1.2.6 settings after `Camxora-1.2.6.exe` was deleted). Draft
  resets to the live release instead of showing a download URL with no row in
  Uploaded installers. See
  `docs/changelog/2026-08-13-stale-draft-missing-installer.md`.
- Draft / Unpublish / delete of a desktop release no longer leave that version
  public. Live snapshot is separate from draft; rollback restores the previous
  live version and unpublishes matching Release notes. See
  `docs/changelog/2026-08-13-force-update-draft-restore.md`.

### Added

- Admin Job Queue ops board APIs: list durable jobs with user/error/worker, recent `image_jobs` failures, and enriched busy-worker metrics. Worker ids include stage label (`CAMXORA_WORKER_NAME`). See `docs/changelog/2026-08-11-job-queue-ops-board.md`.

### Fixed

- Batch create with `structure_mode` `ai_free`/`suno` no longer resurrects Structure Shuffle from saved `shuffleStructure` settings after the request clears it. See `docs/changelog/2026-08-10-suno-structure-mode.md`.
- Image prompt over the **5000**-char allowance is rejected before wallet hold / provider calls (exact API error, no truncation) and does not burn fail-absorb retries. Image-only gate (text/LLM limits unchanged). Image jobs + ledger record routed vs executed provider; profile `image_config.provider` ignored. Migration `083` drops unused OpenAI image fallback hop. See `docs/changelog/2026-08-08-image-provider-truth-prompt-limit.md`.

### Changed

- AI Structure lyric mode uses genre-aware viral layout seeds + batch avoid-list so section sequences vary (still no production-description text in lyric prompts). Seed pool expanded with extra EDM/electronic/dance families. See `docs/changelog/2026-08-08-ai-structure-viral-diversity.md`.

### Added

- Provider credit cards show **today used / remaining** from UTC day-start balance drop (`used_today` on `/admin/provider-key-balances`). See `docs/changelog/2026-08-07-admin-provider-today-usage.md`.
- Admin usage summary includes `credit_pack_revenue_cents` / `credit_pack_payment_count` (fulfilled credit-pack checkout cash) for the dashboard money glance. See `docs/changelog/2026-08-07-admin-dashboard-live-ops.md`.
- `GET /api/v1/health` alias of root `/health` so same-origin admin portals can
  reach health via nginx `/api/` proxy. See
  `docs/changelog/2026-08-06-admin-health-via-api-proxy.md`.
- `GET /health` includes `environment` and `environment_label` (staging→Sandbox,
  production→Production) for admin API Health · System Status. See
  `docs/changelog/2026-08-06-admin-api-health-env-label.md`.

### Changed

- Batch run directories are portable relative keys (`channel\date_album`) only — API no
  longer stores machine absolute `C:\Users\...` / `D:\...` paths for new planning,
  download sync, or local progress sync. Legacy absolute rows are stripped to the
  trailing key on write/heal. Desktop joins its local Suno root. Image job
  `output_image_path` values use the same portable join (no Linux-cwd resolve).
  See `docs/changelog/2026-08-06-app-owned-run-paths-and-missing-mp3.md`.
- Category image samples use **admin VPS packs only** — no fallback to desktop
  `imageBackgroundSamplesDir` / `imageBgSamples` on the API host. Empty packs return
  a clear ValidationError (switch to Prompt only or upload packs).
- `POST /progress/sync-local` rewrites `batches.ok_run_dir` / `alt_run_dir` only when
  `persist_batch_run_dir=true` (Change Run Folder). Background sync updates channel
  assets only and leaves legacy absolute batch paths untouched.

### Fixed

- Image force-regen / NULL `input_image_path`: runtime no longer treats `None` as
  path literal `"None"` (Image reference file does not exist). Falls through to
  Category sample rotation. See
  `docs/changelog/2026-08-06-connect-error-and-null-sample-path.md`.
- Suno success with `audio_id_alt` but empty `audio_url_alt`: synthesize
  `https://cdn1.suno.ai/{id}.mp3`, persist on redownload/reconcile/callback, and
  include those rows in reconcilable polls (previously only healed when *both*
  URLs were missing).

### Added

- SLAI remaining balance on Admin key balances: live credits via `availableUnits / 1_000_000` from `GET https://slai-api.slai.shop/v1/balance`. See `docs/changelog/2026-08-05-slai-provider-key-balance.md`.
- Fail/retry absorb daily budget can be set from Admin Settings (`system_settings.daily_fail_absorb_budget` overrides `PLATFORM_DAILY_FAIL_ABSORB_BUDGET`). See `docs/changelog/2026-08-04-admin-fail-absorb-ui.md`.
- Admin `GET /admin/user-spend`: multi-user est. COGS rollup (wallet + plan-included list value), plan meters, soft-overage / margin-risk alerts, and per-COG breakdown for the User Spent page. See `docs/changelog/2026-08-04-admin-user-spent.md`.
- Admin period quota top-ups: `user_period_quota_topups` migration `081`, `POST /users/{id}/quota-topups`, details `quota_period` snapshot; dual-control credit adjust default off (`PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=0`). See `docs/changelog/2026-08-04-admin-user-quota-topup.md`.
- Pipeline stuck-batch housekeeping: scheduled in-process scan (PipelineStuckAlertService) detects batches with no draft/Suno/image/asset activity for 15+ min (configurable) that aren't fully complete on every configured channel role, and pushes a throttled admin:pipeline_stuck_alert WebSocket alert to every admin (same fan-out as admin:abuse_alert). New GET /admin/pipeline/stuck for an on-demand view of the same detection. See docs/changelog/2026-08-01-pipeline-stuck-batch-alerting.md.
- Restored admin Pipeline Ops API (`/admin/pipeline/board`, batch detail, owner-charged retries via job_queue). See `docs/changelog/2026-08-02-admin-restore-pipeline-ops.md`.
- Pipeline Ops board no longer requires desktop filesystem paths for stage/status; promotes Image → Converter/Streaming/Done from image jobs + stream uploads.
- Admin `GET /admin/provider-key-balances`: remaining credits/money per key-pool label (Suno/DeepSeek/Fal/SLAI live; OpenAI marked unsupported). See `docs/changelog/2026-08-02-admin-provider-key-balances.md` and `docs/changelog/2026-08-05-slai-provider-key-balance.md`.

### Changed

- Phase 1c: `execute_batch` priority 25 (above draft/Suno) + stage multi-workers (`draft`/`suno`/`images` ×2) via `CAMXORA_WORKER_JOB_TYPES` claim filter; shared key pools handle rate-limit failover. See `docs/changelog/2026-08-02-api-phase1c-stage-workers.md`.
- Phase 1b queue follow-ons: image drains + YouTube uploads move to `job_queue`/`camxora-worker`; `execute_batch` fans out per-song `draft`/`suno_submit`; admin `GET /admin/job-queue/metrics` (queue depth, busy workers, `/progress` p95 alerts). See `docs/changelog/2026-08-02-api-phase1b-queue-followons.md`.
- Phase 1 job queue: `POST /batches` and song draft/Suno retries enqueue durable `job_queue` rows; `platform_api.worker` drains them outside uvicorn. Migration `080_job_queue`. See `docs/changelog/2026-08-02-api-phase1-job-queue.md`.
- Phase 0 API capacity: DB pool `min_size=4` / `max_size=8`; `/progress` only ensures image jobs for batches missing rows (skips the previous every-poll heal loop). Pair with uvicorn `--workers 4` on the host. See `docs/changelog/2026-08-02-api-phase0-capacity.md`.

### Fixed

- Progress `GET /progress`: when `active_only` is set, batch over-fetch uses the full cap (100) so Active + Limit can still return up to N active rows after OK/ALT expansion. See `docs/changelog/2026-08-06-progress-filters-composition.md`.

- Admin user detail no longer reports logos/covers as available when the
  stored upload path is missing on disk, which stopped the admin portal from
  requesting those media URLs and logging 404s. See
  docs/changelog/2026-08-04-admin-channel-profile-media-404.md.
- Parallel draft workers no longer invent extra album folders: Album 1 / Album 2
  and run dirs lock once (SQL `COALESCE` first-wins); songs stick to `ok_album`,
  and Suno downloads prefer locked batch dirs. See
  `docs/changelog/2026-08-03-lock-batch-album-run-dirs.md`.
- Desktop installer publish: version comes from the Software Update form /
  draft (Force update checkbox), not from the installer filename. Filename
  parse is auto-fill only; `CamxoraSetup-*.exe` still parses when present.
  See `docs/changelog/2026-08-03-software-update-setup-filename.md`.
- Startup `alembic upgrade heads` now serializes across worker processes via a Postgres advisory lock — with `API_WORKERS` > 1, every worker previously ran migrations independently and concurrently, which raced DDL against other workers' open connection pools and caused a ~30 minute burst of 500s across nearly every endpoint after today's v1.0.9 production deploy. See `docs/changelog/2026-08-01-migration-worker-race-incident.md`.
- Production/sandbox systemd unit templates now set `PYTHONUNBUFFERED=1` — stdout was block-buffered, so error tracebacks (including this incident's) were invisible in `journalctl` until a restart. Same incident doc.
- **Production ran a single uvicorn worker**, confirmed live (--workers 1 on a 6 vCPU/11GB box sitting almost entirely idle), while all heavy background work (image job orchestration, Suno streaming uploads, YouTube uploads, batch orchestration) runs in-process on that same one process via asyncio.create_task()/BackgroundTasks — the planned separate platform_worker queue process doesn't exist yet. A busy batch could starve unrelated simple requests (/auth/refresh, /users/me) sharing the same event loop, matching desktop-client timeout reports across several releases. Bumped to --workers 2 (systemd unit edited + restarted, verified healthy) and persisted via .deploy/secrets.production.env / deploy-script fallback default so it survives future redeploys. See docs/changelog/2026-08-01-production-api-single-worker-bottleneck.md.
- Dual-channel Suno submit no longer crashes on Secondary daily attribution (`increment_usage` now accepts `count` / `include_monthly`). That mismatch was failing after plan deduct and inflating fail/retry absorb on Retry batch. See `docs/changelog/2026-08-03-usage-tracking-count-kwargs.md`.
- Streaming karaoke LRC: retry Suno `get-timestamped-lyrics` after generation (alignments often empty immediately), and fetch LRC on admin MP3 upload retry. See `docs/changelog/2026-08-03-streaming-karaoke-lrc-retry.md`.
- Admin streaming upload-jobs list returns joined user/song/album/batch/publish detail (UI was showing dashes). See `docs/changelog/2026-08-02-admin-streaming-upload-job-details.md`.
- Generate preflight / wallet soft-overage coverage now scales monthly song/image/draft limits by profile add-on slots (same as quota enforcement). Without this, add-on accounts with empty wallets were blocked when base-plan meters looked full (e.g. images 111+16 > 120 while scaled limit is 480). Insufficient-credits messages now show display credits, not micro-units. See `docs/changelog/2026-08-02-subscription-covers-addon-scaling.md`.
- Progress/export can advance once the **background** image is ready; thumbnail is no longer required for `long_ready` / Converter (YouTube upload still needs BG+TH via `compute_youtube_*_ready`). See `docs/changelog/2026-08-02-export-without-waiting-for-thumbnail.md`.
- Suno blocklist sanitize now replaces spaced/hyphenated variants of blocked terms (e.g. `low-light` / `low light` for `lowlight`), so producer-tag rejects are caught before submit. See `docs/changelog/2026-08-02-suno-blocklist-hyphen-variants.md`.
- Dual-channel batches now attribute **daily** song **and draft** usage to Secondary as well as Primary (monthly package still +1 once on Primary; draft slot math unchanged at ≈`2N+1`). Per-channel draft daily used/limit exposed on `/credits/quota-status` (was always `0/0` in UIs). See `docs/changelog/2026-08-02-quota-multi-channel-charging.md`.

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
