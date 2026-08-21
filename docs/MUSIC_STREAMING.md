# Music Streaming Platform

Camxora music streaming uses:

| App | Dev URL | Purpose |
|-----|---------|---------|
| `music_web` | http://localhost:3003 | Public listener UI (`music.camxora.com`) |
| `admin_portal` | http://localhost:5173 | Streaming settings, catalog, upload jobs |
| `platform_api` | http://localhost:8000 | Upload workers + public/admin streaming API |

## Setup

1. From `camxora`, run `./start-services.ps1`
2. Open Admin Portal → **Settings → Streaming** and save Backblaze bucket-scoped credentials
3. Use **Music Streaming** / **Streaming Jobs** in the sidebar to manage catalog takedowns and retries
4. Complete a Suno batch — MP3s upload on callback, covers upload after image jobs
5. Open `music_web` at `http://localhost:3003` to stream published tracks

## API

- Public: `/api/v1/public/streaming/*`
- Admin: `/api/v1/admin/streaming/*`

## Portal UX roadmap

See [`MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`](./MUSIC_STREAMING_PORTAL_ENHANCEMENT.md) for branding, shared auth, pagination, player, lyrics, and library phases.

Protected Play speed (every browser): [`PROTECTED_PLAYBACK_FAST_START.md`](./PROTECTED_PLAYBACK_FAST_START.md). Plan only until implemented.


```
camxora-media/{user_id}/{album_slug}/{song_slug}-{ok|alt}.mp3
camxora-media/{user_id}/{album_slug}/cover.jpg
```
