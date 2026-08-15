# Changelog — Music portal

Public streaming listener UI at `music.camxora.com` — browse, search, genres, player.

**Code:** `music_web/`  
**Policy:** [`docs/CHANGELOG_GUIDE.md`](../docs/CHANGELOG_GUIDE.md)  
**Feature specs:** [`docs/MUSIC_STREAMING.md`](../docs/MUSIC_STREAMING.md), [`docs/STREAMING_CATALOG_ENHANCEMENT.md`](../docs/STREAMING_CATALOG_ENHANCEMENT.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Camxora Music Phase 1: guest marketing home, login-gated `/create` and
  `/explore`, Simple/Advanced Create (two clips, play, MP3 via sunoapi.org),
  music_web-tagged signup. **5 free songs**, then Create shows Upgrade to Pro.
  See `docs/changelog/2026-08-15-music-web-suno-create.md`.
- Create page advanced options: V5/V5.5 model selector, collapsible Advanced
  Options panel (negative tags, vocal gender, style weight, weirdness/creativity,
  audio weight), and auto-generate lyrics & title button. See
  `docs/changelog/2026-08-15-music-web-suno-advanced-options.md`.
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
