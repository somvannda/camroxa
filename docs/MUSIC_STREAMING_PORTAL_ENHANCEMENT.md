# Music streaming portal enhancement

**Status:** in progress (Phase 0–1 started 2026-07-26)  
**Surfaces:** `music_web/` (`music.camxora.com`), `platform_api/` public streaming + auth  
**Related:** [`MUSIC_STREAMING.md`](./MUSIC_STREAMING.md), [`STREAMING_CATALOG_ENHANCEMENT.md`](./STREAMING_CATALOG_ENHANCEMENT.md), [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md)

## Summary

Evolve `music.camxora.com` from a thin public catalog player into a professional Camxora-branded streaming experience: Spotify-like information architecture, marketing-aligned visual identity, shared Camxora user auth, gated playback, library/playlists, and synced lyrics.

## Goals

1. **Same users / same auth** as `user_portal` (`platform_api` JWT + user cookies) — not a second account system.
2. **Camxora identity** — real logo, Inter + Outfit, purple accent (`#7466F1` → `#A259FF` / violet–fuchsia), dark studio surfaces (not Spotify green, not cyan-only utility UI).
3. **Professional chrome** — top header (logo, search, Sign in / Sign up), left nav + Your Library, optional right discovery rail, floating bottom player, proper footer.
4. **Browse public; listen requires login.**
5. **Pagination** for albums, artists, tracks, search, genre lists.
6. **Album / artist pages** comparable to modern streaming heroes (Play, Follow later, discography).
7. **Now-playing right panel** with synced lyrics when a track plays.
8. **Library / playlists / profiles** for signed-in listeners.

## Non-goals (this program)

- HLS / adaptive bitrate (separate infra plan)
- Separate “music-only” user database
- Cloning Spotify green brand / pixel-perfect Spotify skin
- Desktop `camxora_python` changes (catalog publish remains existing pipeline)

## Auth decision (locked)

| Topic | Decision |
|--------|----------|
| Identity | Same `users` table as user portal / desktop |
| Endpoints | Same `/api/v1/auth/*` (login, register, refresh, logout, me) |
| Cookies | **User** cookie names (not admin). Prefer same-origin `/api` proxy on `music.camxora.com`, or parent-domain `.camxora.com` cookies |
| Roles | Listeners = normal users; creators = users who own published `stream_*` rows; admins stay on admin portal |
| Guest | May browse catalog; Play opens auth CTA |

## Target information architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Header: Logo | Search |  [Sign up] [Log in] / Avatar        │
├──────────┬──────────────────────────────┬───────────────────┤
│ Left     │ Main                         │ Right             │
│ Home     │ Home rails / album / artist  │ Trending tracks   │
│ Search   │ Search results               │ Popular artists   │
│ Your     │ Library / playlist           │ Popular albums    │
│ Library  │                              │ Singles           │
│ + Create │                              │ (Now Playing +    │
│ playlist │                              │  synced lyrics    │
│          │                              │  when playing)    │
├──────────┴──────────────────────────────┴───────────────────┤
│ Footer: Product · Music · Legal · Download · © Camxora      │
├─────────────────────────────────────────────────────────────┤
│ Floating player (seek, volume, queue; gated if logged out)  │
└─────────────────────────────────────────────────────────────┘
```

## Phased delivery

### Phase 0 — Pagination foundation *(started)*

- API list responses: `{ items, total, limit, offset }` for albums, artists, search (and genre detail lists where capped).
- Wire `/albums` and `/artists` indexes in `music_web` with **Show more**.
- Unify API base URL helper (fix search vs server client mismatch).

### Phase 1 — Shell & brand *(started)*

- Copy `/camxora-logo.svg`; load Inter + Outfit; purple token override (align with marketing `website/`).
- Top header: logo, search entry, Sign in / Create account → user portal URLs.
- Left nav: Home, Search, Your Library (empty state + “Create playlist” CTA stub).
- Professional footer linking marketing site + legal + portal.
- Stronger floating player chrome (controls scaffold; seek/queue deepen in Phase 4).

### Phase 2 — Auth gate for playback *(started)*

- Music-native `/login` + `/register` (same Camxora users); session cookies via music nginx `/api` proxy.
- `/library` + `/profile` shells on music_web (playlists/likes next).
- User portal honors `?return_to=` / `?next=` for allowlisted music hosts.
- Next: require auth on `play-url`; guest Play → sign-in CTA.

### Phase 3 — Album / artist Spotify-like pages + home rails

- Album hero (large art, **Play / Shuffle**, metadata) — Play-all + Shuffle shipped 2026-07-27; **cover-color hero shipped 2026-07-27**.
- Artist page (`/artists/[user_id]`): hero, popular, discography filters.
- Home right rail: trending / popular (can start with recent + top albums).
- Playing track highlight + equalizer animation on lists — shipped 2026-07-27.

### Phase 4 — Now playing + synced lyrics

- Right panel while playing: cover, about, timed lyrics (LRC or timestamp model).
- Fallback: unscrolled plain lyrics until timestamps exist — **plain lyrics in Now Playing rail shipped 2026-07-27**; karaoke highlight/auto-scroll **only when real LRC is present** (estimated timing removed 2026-07-27). New Suno uploads fetch aligned timestamps and store LRC on `stream_tracks.lyrics`.
- Player: **seek, prev/next, volume**, album queue auto-advance — shipped 2026-07-27; lyrics toggle still pending.
- Album numbered tracklist — shipped 2026-07-27; **inline Show/Hide lyrics removed** (lyrics only in right panel).

### Phase 5 — Library / playlists / profiles

- **Liked Songs** (heart + library list) — shipped 2026-07-27.
- Create first playlist, add/remove tracks, listening history.
- User profile on music portal (public playlists optional).
- Follow artists (optional).

## API changes (Phase 0+)

| Endpoint | Change |
|----------|--------|
| `GET /public/streaming/albums` | Add `total`; keep `limit`/`offset` |
| `GET /public/streaming/artists` | Add `total` |
| `GET /public/streaming/search` | Add `offset` + `total` |
| `GET /public/streaming/genres/{slug}` | Paginate albums/tracks or return totals |
| `GET /public/streaming/tracks/{id}/play-url` | Phase 2: require auth |
| Playlists / library / likes | Phase 5 new routes |

## Brand tokens (music_web)

Align with marketing (not raw shared cyan):

- Primary / accent: violet–purple HSL (~`266 90% 70%`)
- CTA gradient: `from-violet-500 via-purple-500 to-fuchsia-500`
- Logo: `public/camxora-logo.svg`
- Fonts: Inter (`--font-sans`), Outfit (`--font-display`)

## Env (music_web)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` / same-origin `/api` | Platform API |
| `NEXT_PUBLIC_USER_PORTAL_URL` | Sign in / register links (`https://app.camxora.com`) |
| `NEXT_PUBLIC_WEBSITE_URL` | Footer product links (`https://camxora.com`) |
| `NEXT_PUBLIC_CAMXORA_ENV` | Optional sandbox banner |

## Deploy policy

**Sandbox first:** every API / music_web change in this program must be deployed to sandbox (`sync_platform_api_sandbox.py`, `rebuild_music_web_sandbox.py`) before the work is considered done. Production only on explicit request.

## Success criteria

- Guest can browse; signed-in user can play.
- Albums/artists lists paginate without silent truncation.
- Visual identity matches Camxora marketing more than Spotify.
- Footer, header, logo present on all main routes.
- Roadmap phases land behind this doc; update status as each ships.

## Follow-ups / open questions

- Cookie domain strategy for SSO between `app` and `music` without forcing re-login.
- Whether creators get a distinct “Artist” badge on music profiles.
- LRC generation in the desktop/API lyric pipeline vs post-process timestamps.
