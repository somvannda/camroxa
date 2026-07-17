# Music Streaming Catalog Enhancement

Feature spec for evolving `music.camxora.com` from a basic playback portal into a complete streaming experience — starting with **genre** and **Suno track cover art**, plus a roadmap for everything else still missing.

**Status:** PR1–PR2 backend done and deployed; PR3 genre browse API + `music_web` pages shipped (2026-07-17). Admin metadata UI (PR4) still pending.
**Related:** `docs/MUSIC_STREAMING.md`, migration `043_streaming_catalog.py`, `platform_api/services/streaming_upload_service.py`  
**Product scope:** [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md) — **`platform_api`** (upload pipeline, public API), **`music_web`** (player/browse UI), **`admin_portal`** (catalog admin). Desktop client **`camxora_python`** is not required for streaming playback; Electron/`python_app` excluded.

---

## 1. Current state (baseline)

### What works today

| Layer | Capability |
|-------|------------|
| **Upload pipeline** | Suno callback → MP3 download → Backblaze B2 → `stream_tracks` / `stream_albums` |
| **Cover (partial)** | Album cover from Camxora image jobs (thumbnail/background) or profile logo — **not from Suno** |
| **Public API** | Home, album detail, search, play URL (signed MP3) |
| **music_web** | Home + album page + search + bottom player |
| **Admin** | Publish/hide/delete tracks & albums, retry failed upload jobs |

### What is stored on `stream_tracks` today

- `title`, `lyrics`, `variant` (ok/alt), `storage_key`, `size_bytes`, `mime_type`
- `duration_seconds` — **column exists but is never populated**
- **No genre, tags, track number, per-track cover, or Suno clip metadata**

### What is stored on `stream_albums` today

- `album_name`, `album_slug`, `channel_role`, `cover_storage_key`, `publish_status`
- **No genre, description, release year, or label**

### Upstream data we already have (but do not propagate)

| Source | Field | Example use |
|--------|-------|-------------|
| `suno_tasks` | `style` | Genre/style string sent to Suno music API |
| `music_descriptions` | genre/mood/energy text | Batch song description |
| `songs` | `description_id`, `structure_id` | Link back to prompt catalog |
| Suno `record-info` / callback clips | `image_url`, `source_image_url`, `duration`, `tags` | **Not parsed today** |

---

## 2. Goal

Make the public music portal feel like a real streaming product:

1. **Browse by genre** (minimum viable discovery)
2. **Show cover art reliably** — including when Camxora image jobs are off or failed
3. **Display duration** and basic track metadata in the player and lists
4. Lay groundwork for artist pages, lyrics, playlists, and admin metadata editing

---

## 3. Recommendation: metadata model

### Phase A — Ship with genre + Suno cover (this request)

#### Album-level fields (new migration)

| Column | Type | Source |
|--------|------|--------|
| `genre` | `VARCHAR(120)` | Primary: `suno_tasks.style` or `music_descriptions` genre; fallback: parse Suno clip `tags` |
| `description` | `TEXT` nullable | Optional admin edit; default from music description |
| `release_year` | `SMALLINT` nullable | Default: `EXTRACT(YEAR FROM published_at)` |

#### Track-level fields (new migration)

| Column | Type | Source |
|--------|------|--------|
| `genre` | `VARCHAR(120)` nullable | Copy from album or Suno clip `tags` |
| `duration_seconds` | `FLOAT` | Suno clip `duration` from record-info |
| `track_number` | `SMALLINT` nullable | `songs.batch_index + 1` at upload time |
| `cover_storage_key` | `VARCHAR(1024)` nullable | Per-track art when Suno provides distinct images |
| `suno_image_url` | `VARCHAR(1000)` nullable | Original Suno URL (audit/debug; 14-day TTL) |
| `tags` | `TEXT[]` or `JSONB` | Suno clip `tags` split |

> **Design choice:** Genre lives on **both** album and track. Album genre is the browse key; track genre allows OK/ALT variants to differ later.

### Phase B — Discovery & UX (follow-up)

- Genre landing pages: `/genres/edm`, `/genres/lo-fi`
- Artist list + detail (`/artists`, `/artists/{id}`) — API exists, UI is stub
- Album browse page — API exists, UI is stub
- Lyrics panel on track/album page (lyrics already in DB)
- Player: seek bar, duration display, queue, next/previous

### Phase C — Product features (later)

- User accounts, favorites, listening history
- Playlists (user + editorial)
- Explicit/content rating, ISRC, copyright line
- Analytics (plays, top tracks)
- HLS/adaptive streaming (see `docs/PRODUCTION_INFRASTRUCTURE_PLAN.md`)

---

## 4. Suno track cover art

### Problem

Today, cover art depends on **Camxora Auto-Gen Image**. When that is off or fails (common on sandbox), albums show placeholders even though Suno generates artwork.

The Suno API returns cover URLs per generated clip ([callback docs](https://docs.sunoapi.org/suno-api/generate-music-callbacks)):

```json
{
  "audio_url": "https://…/track.mp3",
  "source_audio_url": "https://…/track.mp3",
  "image_url": "https://…/cover.jpeg",
  "source_image_url": "https://…/cover.jpeg",
  "duration": 198.44,
  "tags": "electrifying, rock"
}
```

We already parse audio URLs in `suno_audio_resolver.py` but **ignore image URLs entirely**.

### Recommended cover priority

When a streaming upload runs (callback or reconcile):

```
1. Existing album cover from Camxora image job (keep current behavior)
2. Suno clip image_url / source_image_url → download → B2 cover.jpg
3. Channel profile logo (existing fallback)
4. Platform default placeholder
```

Per-track cover (optional in Phase A):

- Store `stream_tracks.cover_storage_key` when OK and ALT clips have different Suno images
- Album cover = thumbnail track’s art or first successful clip

### Implementation sketch

| Step | Component | Change |
|------|-----------|--------|
| 1 | `suno_client.py` | Add `_extract_clip_image_url()`, `_extract_clip_duration()`, `_extract_clip_tags()` |
| 2 | `suno_audio_resolver.py` | Extend poll/callback parsing to return `SunoClipMetadata` (audio + image + duration + tags) |
| 3 | `suno_tasks` table | Optional columns: `image_url_ok`, `image_url_alt`, `duration_ok`, `duration_alt`, `tags_ok`, `tags_alt` |
| 4 | `streaming_upload_service.py` | After MP3 upload, call `upload_cover_from_suno_image()` if album has no cover |
| 5 | `streaming_repo.py` | Persist genre/duration on upsert |
| 6 | Callbacks | Persist clip metadata when task succeeds (same moment as audio URLs) |

### Image download notes

- Suno files are retained ~14 days — download and store on B2 promptly (same lesson as MP3 URLs)
- Re-use download helper pattern from `suno_audio_resolver.download_suno_mp3_bytes()` with image content-type validation
- Resize to JPEG max 1200px server-side before B2 upload (optional, saves CDN bandwidth)

---

## 5. Genre: where it comes from

Recommended resolution order when creating/updating a stream album or track:

```
1. suno_tasks.style          (what we sent to Suno — often "Tech House", "EDM / Workout Gym")
2. music_descriptions.genre  (from song.description_id → admin/user description catalog)
3. Suno clip tags            (first tag or comma-joined)
4. "Unknown"                 (hide from genre browse, still list on home)
```

Normalize for browse URLs:

- Slug: `slugify(genre)` → `tech-house`, `edm-workout-gym`
- Display: keep original casing from source

### Batch → streaming propagation

At batch creation, description is already on each `songs.description_id`. When `StreamingUploadService._upload_mp3_variant()` runs:

1. Load `suno_tasks.style` + song’s description genre in `get_suno_stream_context()`
2. Write to `stream_albums.genre` on album create
3. Write to `stream_tracks.genre` + `duration_seconds` on track upsert

---

## 6. API & UI changes

### Public API (`streaming_public.py`)

Extend responses:

```typescript
// Album
{
  genre: string | null
  genre_slug: string | null
  description: string | null
  cover_url: string | null
  track_count: number
  total_duration_seconds: number | null
}

// Track
{
  genre: string | null
  duration_seconds: number | null
  track_number: number | null
  cover_url: string | null   // track or album fallback
}
```

New endpoints (Phase A):

- `GET /public/streaming/genres` — list genres with album/track counts
- `GET /public/streaming/genres/{slug}` — albums + recent tracks in genre

### music_web

| Page | Enhancement |
|------|-------------|
| Home | Genre chips row; show duration on track rows |
| Album detail | Genre badge, total duration, release year |
| Search | Filter by genre |
| Player bar | Duration + seek (Phase B) |
| `/genres/[slug]` | New browse page |

### Admin portal (`streaming/catalog.tsx`)

| Enhancement | Priority |
|-------------|----------|
| Cover thumbnail column | A |
| Genre column + inline edit | A |
| Duration column | A |
| Bulk genre assign | B |
| Manual cover upload/replace | B |

---

## 7. Phased delivery plan

### PR1 — Suno metadata extraction (backend only)

- Parse `image_url`, `duration`, `tags` from record-info + callbacks
- Persist on `suno_tasks`
- Unit tests in `test_suno_audio_resolver.py`

### PR2 — Streaming schema + upload pipeline

- Migration: genre, duration, track_number, cover fields
- Upload Suno cover when no Camxora cover exists
- Populate genre from style/description/tags

### PR3 — Public API + music_web genre browse

- Genre list/detail endpoints
- Home genre chips + track duration display
- Album genre badge

### PR4 — Admin metadata editing

- Catalog table columns, inline genre edit, cover preview

---

## 8. Complete streaming website checklist

Use this as the master gap list beyond genre + cover:

| Category | Item | Status |
|----------|------|--------|
| **Metadata** | Genre | Planned (this spec) |
| | Duration | Planned |
| | Track number / disc order | Planned |
| | Release date / year | Planned |
| | Description / credits | Partial (lyrics in DB only) |
| **Artwork** | Suno cover fallback | Planned |
| | Per-track art | Optional Phase A |
| | Admin cover upload | Phase B |
| **Discovery** | Search | Done |
| | Genre browse | **Done** (API + `/genres` pages) |
| | Artist pages | API done, UI stub |
| | Album browse | API done, UI stub |
| | Playlists | Not started |
| | Related / recommended | Not started |
| **Playback** | Signed MP3 URL | Done |
| | Duration + seek | Not started |
| | Queue / autoplay | Not started |
| | Volume / repeat | Not started |
| **Social** | User accounts on portal | Not started |
| | Favorites / library | Not started |
| | Share links | Not started |
| **Admin** | Publish/hide/delete | Done |
| | Metadata edit | Planned |
| | Analytics | Not started |
| **Legal** | DMCA / takedown workflow | Not started |
| | Explicit labeling | Not started |

---

## 9. Key files to touch

| Area | Path |
|------|------|
| Suno clip parsing | `platform_api/clients/suno_client.py`, `platform_api/services/suno_audio_resolver.py` |
| Callback | `platform_api/routers/callbacks.py` |
| Upload | `platform_api/services/streaming_upload_service.py` |
| Catalog DB | `platform_api/repositories/streaming_repo.py` |
| Public API | `platform_api/services/streaming_catalog_service.py`, `platform_api/routers/streaming_public.py` |
| Admin UI | `admin_portal/src/pages/streaming/catalog.tsx` |
| Public UI | `music_web/src/app/**`, `music_web/src/components/**` |
| Schema | New migration after `043_streaming_catalog.py` |

---

## 10. Open questions

1. **OK vs ALT as separate tracks** — Today both variants publish as individual tracks. Do we want genre browse to dedupe by song, or is two tracks per song intentional for the portal?
2. **Genre taxonomy** — Free-text from Suno vs curated enum (EDM, Pop, …)? Recommendation: start free-text + slug; add admin curation later.
3. **Lyrics on public site** — Show full lyrics (licensing) or excerpt only?
4. **Suno image license** — Confirm ToS allows re-hosting cover art on our CDN (same as MP3 re-hosting assumption).

---

## 11. Success criteria (Phase A)

- [ ] Every new Suno batch with streaming enabled gets genre on album + tracks
- [ ] Albums without Camxora image jobs still get cover from Suno when available
- [ ] `duration_seconds` populated for new uploads
- [ ] music_web shows genre on album page and supports `/genres/{slug}` browse
- [ ] Admin catalog shows genre, duration, and cover thumbnail
