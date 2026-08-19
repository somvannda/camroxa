# Changelog — Admin portal

Internal operations UI — AI routing, sample packs, streaming catalog, marketplace, software updates, blog CMS.

**Code:** `admin_portal/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- User detail shows Camxora Music generations in the music.camxora.com
  workspace layout (list, prompt/settings, in-page player). See
  `docs/changelog/2026-08-19-admin-user-generated-songs.md`.
- **Plans** and **Settings → Music Web** can set the unpaid Music daily credit
  pool (default 50 credits ≈ 5 songs; 10 credits per song). Presets for 1 / 3 /
  5 songs or 0 (listen-only). See
  `docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md`.
- Users table infers **Free** for Music-tagged accounts with no paid Music plan
  and shows today's used / 50 daily credits. User detail matches. See
  `docs/changelog/2026-08-18-admin-music-free-daily-display.md`.
- Users table shows a **Tag** column (`Music` / `Studio`) from `users.products`. See
  `docs/changelog/2026-08-18-admin-users-product-tag.md`.
- Users table **Plan** / **Credits** now include Camxora Music subscriptions
  (`web_subscriptions`), plus a **Burned** column. Studio wallet leftovers like
  `0.04 cr` are no longer mistaken for the Music credit pool. **Burned** is
  Music period usage for Music subscribers, and studio wallet debit spend
  (`cr`) for everyone else. See
  `docs/changelog/2026-08-18-admin-users-music-credits.md`.

### Fixed

- Sandbox Users list rebuilt with production **Tag** / used-total **Credits** /
  **Burned** columns (generated-songs hotfix had left `index.tsx` stale). See
  `docs/changelog/2026-08-19-sandbox-admin-users-table-sync.md`.
- **User Spent** Song allowance (`S`) no longer stuck at 0%. API now maps
  tracked `music` usage onto the song meter. See
  `docs/changelog/2026-08-16-user-spent-song-meter.md`.

- **Pipeline Ops**: leftover catalog-archive 403s no longer fill the board as
  live Error rows with a 1s age. Streaming chip still shows `Failed X/Y`. See
  `docs/changelog/2026-08-16-pipeline-stale-streaming-error.md`.

- Software Updates status card lists **Live** and **Draft** as separate blocks,
  each with its own version and download URL (no longer shows the live 1.2.5
  installer under draft 1.2.6). If the draft installer was deleted, the card
  says the file is missing instead of linking a dead URL.
- Software Updates: Draft, Unpublish, and deleting the live installer restore
  the previous public version (website + force update) instead of leaving the
  newest build live. Status card shows live vs draft. See
  `docs/changelog/2026-08-13-force-update-draft-restore.md`.

### Changed

- **Job Queue** (`/job-queue`) is a live ops board: busy workers with stage/users, tabbed Running/Queued/Delayed/Failed jobs (user, batch, error), and a related image-job failure strip. See `docs/changelog/2026-08-11-job-queue-ops-board.md`.
- Usages / User Spent / Finance show Provider and Model as separate labels (avoids GPT-named SLAI models reading as OpenAI). Pipeline image jobs show provider, prompt length, and error (over **5000** max marker). See `docs/changelog/2026-08-08-image-provider-truth-prompt-limit.md`.

### Added

- Provider credit cards: **today used (red) / remaining (green)** from balance drop. See `docs/changelog/2026-08-07-admin-provider-today-usage.md`.
- Dashboard redesigned as a live ops + money glance board: system/workers health, provider credits, income/COGS/profit/credits purchased, and Top 10 spenders (last 30 days). Layout clarified into Platform API / Database / Workers, key-pool row (incl. CALA), per-provider credit cards, then Accounts → Money → Top 10. See `docs/changelog/2026-08-07-admin-dashboard-live-ops.md`.

### Fixed

- Dashboard API Health no longer reads same-origin `/health` (SPA HTML). It
  uses `/api/v1/health` via the nginx API proxy. See
  `docs/changelog/2026-08-06-admin-health-via-api-proxy.md`.

### Added

- Dashboard **API Health · System Status** card and top-bar badge show
  **Sandbox** / **Production** (from `/health` environment fields, with
  hostname fallback). See `docs/changelog/2026-08-06-admin-api-health-env-label.md`.
- Admin Settings **Fail / Retry Absorb** tab: set max platform-absorbed failed gens per user per day (`daily_fail_absorb_budget`). User detail shows today's counter with reset. See `docs/changelog/2026-08-04-admin-fail-absorb-ui.md`.
- **User Spent** page (`/user-spent`): per-user estimated COGS roster with expandable provider × operation breakdown, plan-meter chips, and Over allowance / Margin risk alerts. See `docs/changelog/2026-08-04-admin-user-spent.md`.
- User detail **Plan Quota** card: top up period quotas (draft / Suno / images / export / merge) and wallet credits. Period top-ups expire at billing period end. See `docs/changelog/2026-08-04-admin-user-quota-topup.md`.
- Restored **Pipeline Ops** sidebar page (`/pipeline`): live multi-user board for monitoring active pipelines (stage, stuck, failures, admin retries). See `docs/changelog/2026-08-02-admin-restore-pipeline-ops.md`.
- Dashboard **Provider key balances** panel: remaining credits/money by key name for SLAI, Suno, DeepSeek, OpenAI, Fal (refresh / window focus). See `docs/changelog/2026-08-02-admin-provider-key-balances.md`.
- Job Queue page (`/job-queue`): live depth, busy workers, `/progress` p95, and threshold alerts from `GET /api/v1/admin/job-queue/metrics` (15s poll)
- Users: change password from list (key icon) and user detail Actions — admin reset with session revoke
- Streaming catalog: Plays column on tracks and albums (sum of track plays)
- Streaming catalog: server-side pagination (50/page) with API search + status filters

### Changed

- Sidebar navigation grouped into labeled sections (Overview, Accounts, Billing, Content, Operations, System), including **User Spent**. See `docs/changelog/2026-08-04-admin-sidebar-nav-groups.md`.

### Fixed

- User detail channel logos/covers: do not retry blob fetches on 404; availability
  now comes from API file-existence checks so missing uploads no longer spam
  console 404s. See docs/changelog/2026-08-04-admin-channel-profile-media-404.md.

- Streaming Upload Jobs: API now returns user/song/album/batch/publish fields so cards are not empty dashes. See `docs/changelog/2026-08-02-admin-streaming-upload-job-details.md`.
- Software Updates: Force update publish no longer depends on installer
  filename shape — Version + Force update come from the form; filename parse
  is auto-fill only (`CamxoraSetup-*.exe` still helped when present). See
  `docs/changelog/2026-08-03-software-update-setup-filename.md`.

## [2026-07-25]

### Fixed

- Credits Edit Pricing: surface API 422 validation messages (e.g. local $0 COGS) instead of a generic axios status toast.

### Added

- Prompts page: Music Moods tab (Camxora + user scope) with CRUD, visibility toggle, and usage analytics — mirrors Structures.
- Software Updates page: upload `.zip` / `.exe` / `.msi` installer packages; auto-fills download URL after upload.

## [2026-07-19]

### Added

- Suno blocklist management (Settings tab) and failure metrics for lyrics sanitization rollout.

### Changed

- AI routing section shows stored real costs per operation; Suno lyrics cost aligned to registry.

## [2026-07-18]

### Added

- Suno lyrics sanitize UX support via backend blocklist APIs (admin term registry).

## [2026-07-17]

### Added

- Streaming catalog metadata UI and genre sync for music portal.
