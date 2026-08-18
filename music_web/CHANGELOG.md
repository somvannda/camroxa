# Changelog — Music portal

Public streaming listener UI at `music.camxora.com` — browse, search, genres, player.

**Code:** `music_web/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)  
**Feature specs:** [`docs/MUSIC_STREAMING.md`](../docs/MUSIC_STREAMING.md), [`docs/STREAMING_CATALOG_ENHANCEMENT.md`](../docs/STREAMING_CATALOG_ENHANCEMENT.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Create Simple song description follows Suno V5 limits: UI **1000** (style) with a live counter; API prompt **5000**. Simple uses the description as style. See `docs/changelog/2026-08-18-web-music-simple-prompt-suno-limits.md`.

### Fixed

- Profile no longer shows the “Unlock Unlimited Music Creation” pitch to paid subscribers. It shows the current plan, next billing date, and the other public plans. See `docs/changelog/2026-08-18-music-web-profile-current-plan.md`.
- Create workspace Play/Ready wait until the audio file actually streams (Suno CDN 403 is still Finishing). See `docs/changelog/2026-08-18-music-web-stream-ready.md`.
- Create workspace: clicking a row selects it without playing. Play moves the active selection. Covers show a spinner until Ready, then play; playing shows a tiny purple equalizer on the artwork. Click a title to rename that clip only (Version 1 / Version 2 stay independent). The v5.5 tag sits after Ready. Download badges keep size with a visible spinner overlay; order is playlist, LRC, SRT, MP3, WAV. WAV download no longer fails the MP3-only audio check. Play uses `/stream/ok` and `/stream/alt` so both versions load. See `docs/changelog/2026-08-18-music-web-workspace-follow-playing.md`.
- Session now survives the 15-minute access cookie by refreshing it with the 7-day refresh cookie, same as the user portal. See `docs/changelog/2026-08-18-music-web-session-refresh.md`.
- Create page lyric/style wands: stop sending over-limit lyrics, validate style input before calling the API, and show a clear message when AI assist returns 502. See `docs/changelog/2026-08-17-music-web-generate-assist.md`.
- Create track details show stored vocal gender and slider percents instead of default 0.50; clips are labeled Version 1/2. Play stays on Camxora URLs (no public Suno/B2 redirect). See `docs/changelog/2026-08-17-music-web-create-playback.md`.
- Catalog/Explore play uses the same Camxora stream proxy (signed B2 URLs stay server-side). See `docs/changelog/2026-08-17-catalog-playback-proxy.md`.
- Catalog JSON no longer includes `storage_key` or `suno_audio_id`; the player only loads Camxora play/stream paths. See `docs/changelog/2026-08-17-music-web-no-origin-audio-urls.md`.

### Security

- Sign-up errors from IP farm limits now show the API message instead of a generic 429. See `docs/changelog/2026-08-18-music-web-signup-farm-protection.md`.

### Changed

- Create workspace rows show each clip’s duration before Ready (for example `3:45 · Ready`). See `docs/changelog/2026-08-17-web-music-clip-duration.md`.
- Unconfirmed music-web sessions stay on verify-email with no Create/sidebar; `/create` redirects back. See `docs/changelog/2026-08-17-music-web-email-confirm-lock.md`.
- Checkout iframe only loads CutLuy HTTPS URLs (sandbox + no-referrer). See `docs/changelog/2026-08-17-music-web-checkout-security.md`.
- Music web checkout now owns the post-pay path: poll CutLuy status, fulfill credits, show a success popup, and Close returns to Create. CutLuy is used for KHQR only (no portal payment-link redirect). Plan names show as `Starter (Monthly)`. Credit meter shows remaining / total including top-up packs. See `docs/changelog/2026-08-17-music-web-owned-checkout.md`.

### Added

- Public playlist discovery on Explore and Artists: recent public playlists, creators with public playlists, playlist/track counts on artist cards. See `docs/changelog/2026-08-17-web-music-explore-public-playlists.md`.
- Explore merges streaming catalog artists/tracks with web music public playlist discovery.

### Changed

- Home page (logged out and logged in): featured/recent tracks merge streaming catalog with public playlist tracks (same as Explore); Top artists section added. See `docs/changelog/2026-08-17-web-music-home-discovery.md`.
- Artist list cards show uploaded profile photos for streaming-catalog creators (not only public-playlist creators). See `docs/changelog/2026-08-17-streaming-artist-list-avatars.md`.
- Create track detail: removed LRC/SRT paid-plan and Suno timing info blurb (download buttons unchanged). See `docs/changelog/2026-08-17-remove-lrc-srt-info-copy.md`.
- Removed sandbox environment banner from header. See `docs/changelog/2026-08-17-hide-sandbox-banner.md`.
- Playback requires login; logged-out play attempts redirect to sign in (free users can play). See `docs/changelog/2026-08-17-web-music-lrc-b2-login-playback.md`.
- Logged-in app shell: header height matches sidebar; logo removed from top bar (sidebar only). See `docs/changelog/2026-08-17-logged-in-header-sidebar-alignment.md`.
- Profile page redesign: avatar upload, Free plan badge, Download App link, clearer free-tier credits. See `docs/changelog/2026-08-17-music-web-profile-likes-avatar.md`.
- Heart button saves created tracks via web music likes API.
- Playlist detail hero gradient now wraps the full header including search (fixes hard cut-off above search bar).
- LRC and SRT timed-lyrics downloads require a paid subscription (same gate as MP3/WAV). See `docs/changelog/2026-08-17-web-music-lrc-srt-pro-gate.md`.

### Added

- Create page: rename active workspace via pencil button and inline Save/Cancel. See `docs/changelog/2026-08-17-web-music-workspace-rename.md`.
- Workspace rename/create now edits inline in the same row (dropdown swaps to input).

### Changed

- Create workspace track list: flat rows per Suno variant, Suno cover art, overflow fixes, expanded detail panel settings, playlist add, LRC/SRT karaoke lyric downloads, and model version tags (v5 / v5.5). See `docs/changelog/2026-08-17-web-music-workspace-track-ui.md`.

### Added

- Create page character counters: lyrics **5000**, styles **1000** (Suno style limit).

### Changed

- Auto-generate lyrics draft prompt accepts up to **5000** characters (was 500).

### Added

- Playlists under sidebar Create: `/playlists` list/detail, public/private, add/remove songs.
- CutLuy KHQR checkout modal for subscription and top-up purchases.

See `docs/changelog/2026-08-17-music-web-downloads-playlists-cutluy.md`.

- `/verify-email` page (6-digit code + resend) wired into register flow.
- Shared `AuthFormShell` for compact login/register layout.

### Changed

- Free accounts cannot download MP3/WAV; download buttons open upgrade modal; Free plan copy no longer lists downloads.
- Pricing buttons use plan names (`Get Starter`, etc.); workspace dropdown and style sliders aligned.

See `docs/changelog/2026-08-17-music-web-downloads-playlists-cutluy.md`.

- Sidebar credit card: progress bar for credits used, “Credit reset daily” note, Upgrade to Pro CTA; removed duplicate menu item.

See `docs/changelog/2026-08-17-web-music-unified-daily-credits.md`.

- Unified credit display: free users see daily credits (50/day); subscribers see monthly + top-up credits.

- Radix/shadcn-style dropdowns and selects for user menu, workspaces, and model picker.

See `docs/changelog/2026-08-17-music-web-radix-dropdowns.md`.

- Music Style Tags AI expands user Styles input into Suno-ready production prompts with lyrics/title context.

See `docs/changelog/2026-08-17-web-music-style-prompt-enhancement.md`.

- Section-scoped AI errors (Lyrics/Styles), sidebar account at bottom with name/email/sign out, themed dropdowns.
- Sidebar account stats: line-by-line credits/songs; free tier shows daily free songs in Songs count.

See `docs/changelog/2026-08-17-web-music-section-errors-lyrics-billing.md`.

- Create page UX overhaul: header user dropdown, sidebar account card, model dropdown (V5.5 default), More Options card layout, workspaces.

See `docs/changelog/2026-08-17-web-music-create-ui-workspaces.md`.

- App shell uses user-portal-style fixed sidebar; bottom account/upgrade card stays pinned on every page.
- Create form: collapsible Lyrics / Styles / More Options, taller style field, tick sliders, floating Create CTA (violet theme).

### Fixed

- Login/register duplicate chrome and tall register card; copy no longer implies free signup credits.
- Pricing modal redirects unauthenticated users to login before purchase.

See `docs/changelog/2026-08-16-cutluy-email-auth-ui-fixes.md`.

- Camxora Music Phase 1: guest marketing home, login-gated `/create` and
  `/explore`, Simple/Advanced Create (two clips, play, MP3 via sunoapi.org),
  music_web-tagged signup. **5 free songs**, then Create shows Upgrade to Pro.
  See `docs/changelog/2026-08-15-music-web-suno-create.md`.
- Upgrade modal: When users exceed daily quota (5 songs/day), a modal
  automatically appears showing three paid plans (Starter $10/mo, Creator $30/mo,
  Studio $50/mo) with features comparison. Subscribe buttons ready for future
  payment integration. See `docs/changelog/2026-08-16-web-music-upgrade-modal.md`.
- WAV downloads: removed credit cost notices, now shows "High quality" tooltip (WAV downloads are free)
  See `docs/changelog/2026-08-16-web-music-backblaze-auto-upload.md`.
- Create page advanced options: V5/V5.5 model selector, collapsible Advanced
  Options panel (negative tags, vocal gender, style weight, weirdness/creativity,
  audio weight), and auto-generate lyrics & title button. See
  `docs/changelog/2026-08-15-music-web-suno-advanced-options.md`.
- WAV downloads: Enabled WAV download buttons on both main song list and
  right sidebar. Downloads trigger on-demand WAV conversion via backend API.
  See `docs/changelog/2026-08-16-music-web-wav-downloads.md`.
- Music-native sign-in/up, session via same-origin `/api` cookies; `/library` + `/profile` shells
- Track/album play counts on album pages and track rows
- Player seek scrubber, volume/mute, album queue prev/next + auto-advance
- Album hero Play-all and Shuffle controls
- Contextual Now Playing right rail (About artist, lyrics, Next up) while playing
- Numbered album tracklist (`# / Title / Plays / Time`)
- Playing-row highlight + animated equalizer bars on track lists
- Album hero cover-color atmosphere (blurred art + dominant tint)
- Liked Songs: heart on player/tracks + Your Library list (auth)
- Karaoke-style Now Playing lyrics (auto-scroll + line highlight); removed album inline Show/Hide lyrics

### Changed

- Right Now Playing rail widened (`w-80` → `w-[26rem]`); playing title wraps instead of truncating
- Lyrics panel is static unless the track has real LRC timestamps (no estimated karaoke scroll)
- Browser catalog/player fetches use same-origin `/api` (auth cookies)
- Logo subtitle reads “Music Streaming” (header + footer)
- Playing a track from an album queues the full album

### Changed

- Default API base for server components aligns with platform `:8000` (was `:8100`)

## [2026-07-17]

### Added

- Genre browse pages and public streaming catalog integration (see platform API and admin portal changelogs for backend/admin counterparts).
